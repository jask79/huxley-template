#!/usr/bin/env python3
"""
Color Grader CLI for Huxley Studio Engineer

Programmatic color grading tool for autonomous AI-driven video color grading.
Generates 3D LUTs from lift/gamma/gain parameters, evaluates frame quality,
generates scope visualizations, matches shots to references, and runs full
automated grading pipelines.

Architecture (4-layer, mirrors davinci_resolve.py):
    Layer 1: argparse CLI parser
    Layer 2: handler functions (one per subcommand)
    Layer 3: core classes (ColorGrader, QualityEvaluator, ScopeGenerator,
             ShotMatcher, ReferenceBank, LookLibrary)
    Layer 4: output formatting (JSON or human-readable)

Dependencies (all pre-installed):
    - colour-science (0.4.7)  -- color space math
    - opencv-python (4.13.0)  -- frame analysis, scopes
    - color-matcher (0.6.0)   -- shot matching
    - numpy (2.4.2)           -- array math
    - stdlib only otherwise

Usage:
    python3 tools/color_grader.py generate-lut --lift 0.02,0.0,-0.03 ...
    python3 tools/color_grader.py cdl --slope 1.1,1.0,0.95 ...
    python3 tools/color_grader.py evaluate --frame frame.png
    python3 tools/color_grader.py scopes --frame frame.png --types waveform,vectorscope
    python3 tools/color_grader.py match --source src.png --reference ref.png
    python3 tools/color_grader.py grade --frame frame.png --workflow full
    python3 tools/color_grader.py looks list
    python3 tools/color_grader.py refs add frame.png --name hero-shot
"""

import argparse
import colorsys
import hashlib
import json
import logging
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

logger = logging.getLogger("color_grader")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ColorGraderError(Exception):
    """Base exception for color grader errors."""
    pass

class InvalidParameterError(ColorGraderError):
    """Invalid grading parameter value."""
    pass

class FileNotFoundError_(ColorGraderError):
    """Required file not found."""
    pass

class ProcessingError(ColorGraderError):
    """Image processing failed."""
    pass

# ---------------------------------------------------------------------------
# Layer 3: Core Classes
# ---------------------------------------------------------------------------

class ColorGrader:
    """Core LUT generation engine using numpy-vectorized color math.

    All color math operates in 0.0-1.0 normalized float space.
    The .cube format uses R as inner loop, G middle, B outer.
    """

    @staticmethod
    def apply_lift(rgb: np.ndarray, lift: Tuple[float, float, float]) -> np.ndarray:
        """Apply lift (shadow offset) to RGB array.

        Args:
            rgb: Array of shape (..., 3) in 0-1 range.
            lift: (R, G, B) additive offset, typically -0.5 to +0.5.

        Returns:
            Adjusted RGB array, clamped to 0-1.
        """
        result = rgb + np.array(lift, dtype=np.float64)
        return np.clip(result, 0.0, 1.0)

    @staticmethod
    def apply_gamma(rgb: np.ndarray, gamma: Tuple[float, float, float]) -> np.ndarray:
        """Apply gamma (midtone adjustment) to RGB array.

        Formula: out = in ^ (1/gamma)
        gamma > 1.0 brightens midtones, < 1.0 darkens.

        Args:
            rgb: Array of shape (..., 3) in 0-1 range, already clamped.
            gamma: (R, G, B) gamma values, typically 0.1 to 5.0.

        Returns:
            Adjusted RGB array.
        """
        g = np.array(gamma, dtype=np.float64)
        # Avoid division by zero; values <= 0 treated as very small
        safe_g = np.where(g > 0.001, g, 0.001)
        exponents = 1.0 / safe_g
        return np.clip(np.power(rgb, exponents), 0.0, 1.0)

    @staticmethod
    def apply_gain(rgb: np.ndarray, gain: Tuple[float, float, float]) -> np.ndarray:
        """Apply gain (highlight multiplier) to RGB array.

        Args:
            rgb: Array of shape (..., 3) in 0-1 range.
            gain: (R, G, B) multipliers, typically 0.0 to 2.0.

        Returns:
            Adjusted RGB array, clamped to 0-1.
        """
        result = rgb * np.array(gain, dtype=np.float64)
        return np.clip(result, 0.0, 1.0)

    @staticmethod
    def adjust_saturation(rgb: np.ndarray, factor: float) -> np.ndarray:
        """Adjust saturation while preserving Rec.709 luminance.

        Args:
            rgb: Array of shape (..., 3) in 0-1 range.
            factor: 0.0=grayscale, 1.0=original, 2.0=double saturation.

        Returns:
            Adjusted RGB array, clamped to 0-1.
        """
        # Rec.709 luma coefficients
        luma = (0.2126 * rgb[..., 0] +
                0.7152 * rgb[..., 1] +
                0.0722 * rgb[..., 2])
        luma = luma[..., np.newaxis]
        result = luma + (rgb - luma) * factor
        return np.clip(result, 0.0, 1.0)

    @staticmethod
    def hue_shift(rgb: np.ndarray, degrees: float) -> np.ndarray:
        """Shift hue by given degrees while preserving saturation and value.

        Args:
            rgb: Array of shape (N, 3) in 0-1 range.
            degrees: Hue rotation in degrees.

        Returns:
            Adjusted RGB array.
        """
        if abs(degrees) < 0.001:
            return rgb

        original_shape = rgb.shape
        flat = rgb.reshape(-1, 3)
        result = np.empty_like(flat)

        shift_frac = degrees / 360.0

        for i in range(flat.shape[0]):
            r, g, b = float(flat[i, 0]), float(flat[i, 1]), float(flat[i, 2])
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            h = (h + shift_frac) % 1.0
            r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
            result[i] = [r2, g2, b2]

        return np.clip(result.reshape(original_shape), 0.0, 1.0)

    @staticmethod
    def color_temperature(rgb: np.ndarray, kelvin: float) -> np.ndarray:
        """Adjust color temperature using simplified Planckian approximation.

        5600K = neutral daylight. Lower = warmer (orange), higher = cooler (blue).

        Args:
            rgb: Array of shape (..., 3) in 0-1 range.
            kelvin: Target color temperature, 2000-10000.

        Returns:
            Adjusted RGB array, clamped to 0-1.
        """
        if abs(kelvin - 5600.0) < 1.0:
            return rgb

        result = rgb.copy()

        if kelvin < 5600:
            factor = (5600 - kelvin) / 3600.0
            result[..., 0] *= (1.0 + 0.3 * factor)  # boost red
            result[..., 2] *= (1.0 - 0.3 * factor)  # reduce blue
        else:
            factor = (kelvin - 5600) / 4400.0
            result[..., 0] *= (1.0 - 0.2 * factor)  # reduce red
            result[..., 2] *= (1.0 + 0.2 * factor)  # boost blue

        return np.clip(result, 0.0, 1.0)

    @staticmethod
    def apply_cdl(rgb: np.ndarray,
                  slope: Tuple[float, float, float],
                  offset: Tuple[float, float, float],
                  power: Tuple[float, float, float],
                  saturation: float = 1.0) -> np.ndarray:
        """Apply ASC CDL (Color Decision List) formula.

        ASC standard: out = clamp((in * slope + offset) ^ power)
        Saturation applied afterward via Rec.709 luma.

        Args:
            rgb: Array of shape (..., 3) in 0-1 range.
            slope: Per-channel multiplier.
            offset: Per-channel additive.
            power: Per-channel exponent.
            saturation: Global saturation factor.

        Returns:
            Adjusted RGB array, clamped to 0-1.
        """
        result = rgb * np.array(slope, dtype=np.float64) + np.array(offset, dtype=np.float64)
        result = np.clip(result, 0.0, 1.0)
        result = np.power(result, np.array(power, dtype=np.float64))
        result = np.clip(result, 0.0, 1.0)
        if abs(saturation - 1.0) > 0.001:
            result = ColorGrader.adjust_saturation(result, saturation)
        return result

    def generate_identity_cube(self, size: int = 33) -> np.ndarray:
        """Generate an identity (pass-through) LUT cube as a numpy array.

        Returns array of shape (size^3, 3) with values in 0-1.
        Iteration order: B outer, G middle, R inner (standard .cube order).
        """
        steps = np.linspace(0.0, 1.0, size, dtype=np.float64)
        # meshgrid with indexing='ij' gives B, G, R order for outer->inner
        b_grid, g_grid, r_grid = np.meshgrid(steps, steps, steps, indexing='ij')
        cube = np.stack([r_grid.ravel(), g_grid.ravel(), b_grid.ravel()], axis=-1)
        return cube

    def generate_lut(self,
                     lift: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                     gamma: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                     gain: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                     saturation: float = 1.0,
                     hue_shift_deg: float = 0.0,
                     temperature: float = 5600.0,
                     size: int = 33) -> np.ndarray:
        """Generate a graded LUT cube from parameters.

        Applies transforms in order: lift -> clamp -> gamma -> gain ->
        saturation -> hue shift -> temperature -> clamp.

        Args:
            lift: Per-channel shadow offset.
            gamma: Per-channel midtone power.
            gain: Per-channel highlight multiplier.
            saturation: Saturation factor (1.0 = neutral).
            hue_shift_deg: Hue rotation in degrees.
            temperature: Color temperature in Kelvin.
            size: Cube dimension (17, 33, or 64).

        Returns:
            Array of shape (size^3, 3) with graded values.
        """
        cube = self.generate_identity_cube(size)

        cube = self.apply_lift(cube, lift)
        cube = self.apply_gamma(cube, gamma)
        cube = self.apply_gain(cube, gain)

        if abs(saturation - 1.0) > 0.001:
            cube = self.adjust_saturation(cube, saturation)

        if abs(hue_shift_deg) > 0.001:
            cube = self.hue_shift(cube, hue_shift_deg)

        if abs(temperature - 5600.0) > 1.0:
            cube = self.color_temperature(cube, temperature)

        return np.clip(cube, 0.0, 1.0)

    def generate_cdl_lut(self,
                         slope: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                         offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                         power: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                         saturation: float = 1.0,
                         size: int = 33) -> np.ndarray:
        """Generate a CDL-graded LUT cube.

        Args:
            slope: Per-channel multiplier.
            offset: Per-channel additive offset.
            power: Per-channel exponent.
            saturation: Saturation factor.
            size: Cube dimension.

        Returns:
            Array of shape (size^3, 3) with CDL-graded values.
        """
        cube = self.generate_identity_cube(size)
        return self.apply_cdl(cube, slope, offset, power, saturation)

    @staticmethod
    def write_cube_file(cube: np.ndarray, output_path: str,
                        title: str = "Huxley Color Grade",
                        size: int = 33) -> None:
        """Write a numpy LUT cube to .cube file format.

        Args:
            cube: Array of shape (size^3, 3) with values in 0-1.
            output_path: Path for the output .cube file.
            title: LUT title string.
            size: Cube dimension (must match cube array).
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, 'w') as f:
            f.write(f'TITLE "{title}"\n')
            f.write(f'LUT_3D_SIZE {size}\n\n')

            for i in range(cube.shape[0]):
                r, g, b = cube[i]
                f.write(f'{r:.6f} {g:.6f} {b:.6f}\n')

        logger.info("Wrote LUT to %s (%d entries)", output_path, cube.shape[0])

    @staticmethod
    def write_cdl_xml(slope: Tuple[float, float, float],
                      offset: Tuple[float, float, float],
                      power: Tuple[float, float, float],
                      saturation: float,
                      output_path: str,
                      correction_id: str = "shot_001") -> None:
        """Write ASC CDL XML format.

        Args:
            slope: Per-channel slope values.
            offset: Per-channel offset values.
            power: Per-channel power values.
            saturation: Saturation value.
            output_path: Path for the output .cdl file.
            correction_id: ID attribute for the ColorCorrection element.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ColorDecisionList xmlns="urn:ASC:CDL:v1.01">
  <ColorDecision>
    <ColorCorrection id="{correction_id}">
      <SOPNode>
        <Slope>{slope[0]:.6f} {slope[1]:.6f} {slope[2]:.6f}</Slope>
        <Offset>{offset[0]:.6f} {offset[1]:.6f} {offset[2]:.6f}</Offset>
        <Power>{power[0]:.6f} {power[1]:.6f} {power[2]:.6f}</Power>
      </SOPNode>
      <SatNode><Saturation>{saturation:.6f}</Saturation></SatNode>
    </ColorCorrection>
  </ColorDecision>
</ColorDecisionList>
"""
        with open(output, 'w') as f:
            f.write(xml)

        logger.info("Wrote CDL XML to %s", output_path)

    @staticmethod
    def apply_lut_to_frame(frame: np.ndarray, cube: np.ndarray,
                           size: int = 33) -> np.ndarray:
        """Apply a 3D LUT to an image frame using trilinear interpolation.

        Args:
            frame: BGR image (OpenCV format), uint8 or float.
            cube: LUT array of shape (size^3, 3), values 0-1.
            size: Cube dimension.

        Returns:
            Graded BGR image as uint8.
        """
        # Normalize to 0-1 float RGB
        if frame.dtype == np.uint8:
            img = frame.astype(np.float64) / 255.0
        else:
            img = frame.astype(np.float64)

        # BGR to RGB
        img = img[..., ::-1]

        # Reshape cube to 3D: (size, size, size, 3) with B outer, G mid, R inner
        lut_3d = cube.reshape(size, size, size, 3)

        h, w, _ = img.shape
        flat = img.reshape(-1, 3)

        # Scale to cube coordinates
        scale = float(size - 1)
        coords = flat * scale

        # Floor and ceil indices
        c0 = np.floor(coords).astype(np.int32)
        c1 = np.minimum(c0 + 1, size - 1)
        c0 = np.clip(c0, 0, size - 1)

        # Fractional parts
        frac = coords - c0.astype(np.float64)

        r0, g0, b0 = c0[:, 0], c0[:, 1], c0[:, 2]
        r1, g1, b1 = c1[:, 0], c1[:, 1], c1[:, 2]
        fr, fg, fb = frac[:, 0], frac[:, 1], frac[:, 2]

        # Trilinear interpolation (8 corners of the cube cell)
        # LUT indexed as [b, g, r]
        c000 = lut_3d[b0, g0, r0]
        c001 = lut_3d[b0, g0, r1]
        c010 = lut_3d[b0, g1, r0]
        c011 = lut_3d[b0, g1, r1]
        c100 = lut_3d[b1, g0, r0]
        c101 = lut_3d[b1, g0, r1]
        c110 = lut_3d[b1, g1, r0]
        c111 = lut_3d[b1, g1, r1]

        fr = fr[:, np.newaxis]
        fg = fg[:, np.newaxis]
        fb = fb[:, np.newaxis]

        # Interpolate along R
        c00 = c000 * (1 - fr) + c001 * fr
        c01 = c010 * (1 - fr) + c011 * fr
        c10 = c100 * (1 - fr) + c101 * fr
        c11 = c110 * (1 - fr) + c111 * fr

        # Interpolate along G
        c0_ = c00 * (1 - fg) + c01 * fg
        c1_ = c10 * (1 - fg) + c11 * fg

        # Interpolate along B
        result = c0_ * (1 - fb) + c1_ * fb
        result = np.clip(result, 0.0, 1.0)

        # Reshape back and convert RGB to BGR
        result = result.reshape(h, w, 3)[..., ::-1]
        return (result * 255.0).astype(np.uint8)


class QualityEvaluator:
    """Evaluate frame color quality using objective metrics.

    All analysis works on BGR images loaded via OpenCV.
    """

    @staticmethod
    def evaluate(frame: np.ndarray,
                 reference: Optional[np.ndarray] = None,
                 previous_frame: Optional[np.ndarray] = None,
                 ai_eval: bool = False) -> Dict[str, Any]:
        """Run full quality evaluation on a frame.

        Args:
            frame: BGR image (uint8).
            reference: Optional BGR reference image for comparison.
            previous_frame: Optional BGR previous frame for temporal check.
            ai_eval: Whether to run AI vision evaluation (stubbed).

        Returns:
            Dictionary with metrics and overall score.
        """
        results: Dict[str, Any] = {}

        # --- Clipping ---
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        total_pixels = float(gray.size)

        blacks_pct = float(np.sum(gray == 0)) / total_pixels * 100.0
        whites_pct = float(np.sum(gray == 255)) / total_pixels * 100.0

        # Per-channel clipping
        b, g, r = cv2.split(frame)
        r_clip = (float(np.sum(r == 0)) + float(np.sum(r == 255))) / total_pixels * 100.0
        g_clip = (float(np.sum(g == 0)) + float(np.sum(g == 255))) / total_pixels * 100.0
        b_clip = (float(np.sum(b == 0)) + float(np.sum(b == 255))) / total_pixels * 100.0

        clip_pass = blacks_pct < 2.0 and whites_pct < 2.0
        results["clipping"] = {
            "blacks_pct": round(blacks_pct, 2),
            "whites_pct": round(whites_pct, 2),
            "r_clip_pct": round(r_clip, 2),
            "g_clip_pct": round(g_clip, 2),
            "b_clip_pct": round(b_clip, 2),
            "pass": clip_pass,
        }

        # --- Color cast ---
        mean_r = float(r.mean())
        mean_g = float(g.mean())
        mean_b = float(b.mean())
        max_diff = max(abs(mean_r - mean_g), abs(mean_g - mean_b), abs(mean_b - mean_r))
        cast_pass = max_diff < 15.0

        results["color_cast"] = {
            "mean_rgb": [round(mean_r, 1), round(mean_g, 1), round(mean_b, 1)],
            "max_diff": round(max_diff, 1),
            "pass": cast_pass,
        }

        # --- Contrast ---
        sorted_gray = np.sort(gray.ravel())
        n = len(sorted_gray)
        p5 = int(sorted_gray[int(n * 0.05)])
        p95 = int(sorted_gray[int(n * 0.95)])
        contrast_range = p95 - p5
        contrast_pass = contrast_range > 80

        results["contrast"] = {
            "range": contrast_range,
            "p5": p5,
            "p95": p95,
            "pass": contrast_pass,
        }

        # --- Saturation ---
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mean_sat = float(hsv[:, :, 1].mean())
        sat_pass = 30.0 < mean_sat < 200.0

        results["saturation"] = {
            "mean": round(mean_sat, 1),
            "pass": sat_pass,
        }

        # --- Skin tones (simple HSV range detection, no ML) ---
        h_chan = hsv[:, :, 0].astype(np.float32)
        s_chan = hsv[:, :, 1].astype(np.float32)
        v_chan = hsv[:, :, 2].astype(np.float32)

        # OpenCV HSV: H is 0-179, S is 0-255, V is 0-255
        # Skin hue range: 0-25 in OpenCV (= 0-50 degrees)
        # Skin sat: 20-80% of 255 => ~51-204
        skin_mask = ((h_chan >= 0) & (h_chan <= 25) &
                     (s_chan >= 51) & (s_chan <= 204) &
                     (v_chan >= 50) & (v_chan <= 240))

        skin_pct = float(np.sum(skin_mask)) / total_pixels * 100.0
        skin_detected = skin_pct > 1.0  # At least 1% of frame

        skin_result: Dict[str, Any] = {"detected": skin_detected}
        if skin_detected:
            skin_hue_mean = float(h_chan[skin_mask].mean()) * 2.0  # Convert to 0-360
            skin_sat_mean = float(s_chan[skin_mask].mean()) / 255.0 * 100.0
            skin_val_mean = float(v_chan[skin_mask].mean()) / 255.0 * 100.0
            skin_pass = (0 <= skin_hue_mean <= 50 and
                         20 <= skin_sat_mean <= 80)
            skin_result.update({
                "coverage_pct": round(skin_pct, 1),
                "mean_hue_deg": round(skin_hue_mean, 1),
                "mean_sat_pct": round(skin_sat_mean, 1),
                "mean_val_pct": round(skin_val_mean, 1),
                "pass": skin_pass,
            })
        else:
            skin_result["pass"] = True  # No skin = no issue

        results["skin_tones"] = skin_result

        # --- Temporal consistency ---
        temporal_result: Dict[str, Any] = {"checked": False}
        if previous_frame is not None:
            prev_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
            # Resize if dimensions differ
            if prev_gray.shape != gray.shape:
                prev_gray = cv2.resize(prev_gray, (gray.shape[1], gray.shape[0]))
            mean_diff = float(np.mean(np.abs(gray.astype(np.float32) -
                                              prev_gray.astype(np.float32))))
            temporal_pass = mean_diff < 5.0
            temporal_result = {
                "checked": True,
                "mean_luma_diff": round(mean_diff, 2),
                "pass": temporal_pass,
            }

        results["temporal"] = temporal_result

        # --- AI Vision evaluation (stubbed) ---
        ai_score = None
        if ai_eval:
            # Placeholder: AI vision evaluation requires --ai flag and GEMINI_API_KEY
            ai_score = 75
            logger.info("AI evaluation stubbed at score 75. "
                        "Full Gemini vision integration pending.")

        results["ai_score"] = ai_score

        # --- Overall score ---
        # Each metric contributes to the overall score
        metric_scores = []
        if clip_pass:
            metric_scores.append(100)
        else:
            # Penalize proportionally to clipping
            clip_penalty = min(blacks_pct + whites_pct, 20.0) * 5.0
            metric_scores.append(max(0, 100 - clip_penalty))

        if cast_pass:
            metric_scores.append(100)
        else:
            cast_penalty = min(max_diff, 50.0) * 2.0
            metric_scores.append(max(0, 100 - cast_penalty))

        if contrast_pass:
            metric_scores.append(100)
        else:
            contrast_penalty = max(0, 80 - contrast_range) * 1.5
            metric_scores.append(max(0, 100 - contrast_penalty))

        if sat_pass:
            metric_scores.append(100)
        else:
            metric_scores.append(60)

        if skin_result.get("pass", True):
            metric_scores.append(100)
        else:
            metric_scores.append(70)

        overall_score = int(round(sum(metric_scores) / len(metric_scores)))
        overall_pass = all(results[k].get("pass", True)
                           for k in ["clipping", "color_cast", "contrast",
                                     "saturation", "skin_tones"])

        results["overall_score"] = overall_score
        results["overall_pass"] = overall_pass

        return results


class ScopeGenerator:
    """Generate video scope visualizations from frames.

    All scopes are rendered as images using OpenCV drawing functions
    (no matplotlib dependency).
    """

    @staticmethod
    def generate_waveform(frame: np.ndarray, width: int = 0) -> np.ndarray:
        """Generate a luma waveform monitor visualization.

        X-axis = horizontal position in frame.
        Y-axis = brightness level (0 at bottom, 255 at top).

        Args:
            frame: BGR image (uint8).
            width: Output width (0 = match frame width).

        Returns:
            Grayscale waveform image (256 rows x width cols).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if width > 0 and width != gray.shape[1]:
            gray = cv2.resize(gray, (width, gray.shape[0]))

        w = gray.shape[1]
        waveform = np.zeros((256, w), dtype=np.uint8)

        for col in range(w):
            column = gray[:, col]
            hist, _ = np.histogram(column, bins=256, range=(0, 256))
            for val in range(256):
                if hist[val] > 0:
                    intensity = min(255, hist[val] * 8)  # Brighten dots
                    waveform[255 - val, col] = max(
                        waveform[255 - val, col], intensity)

        return waveform

    @staticmethod
    def generate_vectorscope(frame: np.ndarray, size: int = 512) -> np.ndarray:
        """Generate a vectorscope visualization.

        Circular plot showing hue (angle) and saturation (radius).

        Args:
            frame: BGR image (uint8).
            size: Output image size (square).

        Returns:
            BGR vectorscope image.
        """
        # Downsample for speed
        max_dim = 512
        h, w = frame.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        scope = np.zeros((size, size, 3), dtype=np.uint8)
        scope[:] = (20, 20, 20)  # Dark gray background

        center = size // 2
        max_radius = center - 20

        # Draw graticule (circle and crosshairs)
        cv2.circle(scope, (center, center), max_radius, (60, 60, 60), 1)
        cv2.circle(scope, (center, center), max_radius // 2, (40, 40, 40), 1)
        cv2.line(scope, (center, 20), (center, size - 20), (40, 40, 40), 1)
        cv2.line(scope, (20, center), (size - 20, center), (40, 40, 40), 1)

        # Draw skin tone line (I-line: roughly from center toward orange)
        skin_angle = math.radians(123)  # ~123 deg in vectorscope convention
        skin_x = int(center + max_radius * math.cos(skin_angle))
        skin_y = int(center - max_radius * math.sin(skin_angle))
        cv2.line(scope, (center, center), (skin_x, skin_y), (0, 100, 100), 1)

        # Plot pixels
        flat_h = hsv[:, :, 0].ravel().astype(np.float64)
        flat_s = hsv[:, :, 1].ravel().astype(np.float64)

        # OpenCV hue is 0-179, convert to radians
        angles = flat_h * 2.0 * math.pi / 180.0
        radii = (flat_s / 255.0) * max_radius

        px = (center + radii * np.cos(angles)).astype(np.int32)
        py = (center - radii * np.sin(angles)).astype(np.int32)

        valid = ((px >= 0) & (px < size) & (py >= 0) & (py < size))
        px = px[valid]
        py = py[valid]

        # Accumulate brightness
        for i in range(len(px)):
            x, y = int(px[i]), int(py[i])
            scope[y, x] = np.minimum(
                scope[y, x].astype(np.int16) + np.array([15, 25, 15], dtype=np.int16),
                255
            ).astype(np.uint8)

        return scope

    @staticmethod
    def generate_parade(frame: np.ndarray, width: int = 0) -> np.ndarray:
        """Generate an RGB parade (three channel waveforms side by side).

        Args:
            frame: BGR image (uint8).
            width: Width per channel (0 = match frame width).

        Returns:
            BGR parade image (256 rows x 3*width cols).
        """
        b, g, r = cv2.split(frame)
        channel_width = width if width > 0 else frame.shape[1]

        if channel_width != frame.shape[1]:
            r = cv2.resize(r, (channel_width, frame.shape[0]))
            g = cv2.resize(g, (channel_width, frame.shape[0]))
            b = cv2.resize(b, (channel_width, frame.shape[0]))

        parade = np.zeros((256, channel_width * 3, 3), dtype=np.uint8)

        # Red channel
        for col in range(channel_width):
            hist, _ = np.histogram(r[:, col], bins=256, range=(0, 256))
            for val in range(256):
                if hist[val] > 0:
                    intensity = min(255, hist[val] * 8)
                    parade[255 - val, col, 2] = max(
                        parade[255 - val, col, 2], intensity)

        # Green channel
        offset = channel_width
        for col in range(channel_width):
            hist, _ = np.histogram(g[:, col], bins=256, range=(0, 256))
            for val in range(256):
                if hist[val] > 0:
                    intensity = min(255, hist[val] * 8)
                    parade[255 - val, offset + col, 1] = max(
                        parade[255 - val, offset + col, 1], intensity)

        # Blue channel
        offset = channel_width * 2
        for col in range(channel_width):
            hist, _ = np.histogram(b[:, col], bins=256, range=(0, 256))
            for val in range(256):
                if hist[val] > 0:
                    intensity = min(255, hist[val] * 8)
                    parade[255 - val, offset + col, 0] = max(
                        parade[255 - val, offset + col, 0], intensity)

        return parade

    @staticmethod
    def generate_histogram(frame: np.ndarray,
                           width: int = 512,
                           height: int = 256) -> np.ndarray:
        """Generate an RGB histogram visualization.

        Args:
            frame: BGR image (uint8).
            width: Output width.
            height: Output height.

        Returns:
            BGR histogram image.
        """
        hist_img = np.zeros((height, width, 3), dtype=np.uint8)
        hist_img[:] = (20, 20, 20)

        colors = [(0, 0, 200), (0, 200, 0), (200, 0, 0)]  # BGR for R, G, B display
        channels = cv2.split(frame)  # b, g, r

        # Compute all histograms and find global max for normalization
        hists = []
        for ch in channels:
            h = cv2.calcHist([ch], [0], None, [256], [0, 256]).ravel()
            hists.append(h)

        max_val = max(h.max() for h in hists)
        if max_val == 0:
            return hist_img

        x_scale = width / 256.0
        y_scale = (height - 10) / max_val

        # Draw in order B, G, R so red is on top
        for ch_idx, (hist, color) in enumerate(zip(hists, colors)):
            points = []
            for i in range(256):
                x = int(i * x_scale)
                y = height - int(hist[i] * y_scale)
                points.append((x, max(0, y)))

            for i in range(1, len(points)):
                cv2.line(hist_img, points[i - 1], points[i], color, 1,
                         cv2.LINE_AA)

        return hist_img


class ShotMatcher:
    """Match shot colors to a reference using the color-matcher library."""

    @staticmethod
    def match(source: np.ndarray, reference: np.ndarray,
              method: str = "mkl") -> np.ndarray:
        """Transfer color from reference to source.

        Args:
            source: BGR source image (uint8).
            reference: BGR reference image (uint8).
            method: Matching algorithm ('mkl', 'reinhard', 'hm-mvgd-hm').

        Returns:
            Color-matched BGR image (uint8).
        """
        try:
            from color_matcher import ColorMatcher
        except ImportError:
            raise ColorGraderError(
                "color-matcher not installed. Run: pip install color-matcher")

        cm = ColorMatcher()
        # color-matcher expects RGB
        src_rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
        ref_rgb = cv2.cvtColor(reference, cv2.COLOR_BGR2RGB)

        result_rgb = cm.transfer(src=src_rgb, ref=ref_rgb, method=method)
        # color-matcher may return float64; convert to uint8 for OpenCV
        if result_rgb.dtype != np.uint8:
            result_rgb = np.clip(result_rgb, 0, 255).astype(np.uint8)
        result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
        return result_bgr

    @staticmethod
    def generate_corrective_lut(source: np.ndarray, reference: np.ndarray,
                                method: str = "mkl",
                                size: int = 33) -> np.ndarray:
        """Generate a corrective .cube LUT by passing an identity cube through
        the color-matcher transform.

        Creates a size^3 identity cube as an image, passes it through
        color_matcher.transfer(), and returns the transformed cube.

        Args:
            source: BGR source image (uint8).
            reference: BGR reference image (uint8).
            method: Matching algorithm.
            size: LUT cube dimension.

        Returns:
            Array of shape (size^3, 3) with corrective LUT values in 0-1.
        """
        try:
            from color_matcher import ColorMatcher
        except ImportError:
            raise ColorGraderError(
                "color-matcher not installed. Run: pip install color-matcher")

        # Create identity cube as image
        grader = ColorGrader()
        identity = grader.generate_identity_cube(size)

        # Reshape to fake image: (size^3, 1, 3) and scale to 0-255 uint8 RGB
        cube_img = (identity * 255.0).astype(np.uint8).reshape(-1, 1, 3)

        # color-matcher expects RGB
        src_rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
        ref_rgb = cv2.cvtColor(reference, cv2.COLOR_BGR2RGB)

        cm = ColorMatcher()
        matched_cube = cm.transfer(src=cube_img, ref=ref_rgb, method=method)

        # Normalize back to 0-1 (clip first as color-matcher may exceed 0-255)
        result = np.clip(matched_cube, 0, 255).reshape(-1, 3).astype(np.float64) / 255.0
        return np.clip(result, 0.0, 1.0)


class LookLibrary:
    """Built-in creative look presets.

    Each preset defines lift/gamma/gain/saturation/temperature parameters
    that can be applied as a LUT.
    """

    PRESETS: Dict[str, Dict[str, Any]] = {
        "cinematic-teal-orange": {
            "description": "Classic teal shadows + orange highlights, Hollywood blockbuster look",
            "lift": (-0.05, 0.0, 0.08),
            "gamma": (1.0, 1.0, 0.85),
            "gain": (1.15, 1.08, 0.90),
            "saturation": 1.0,
            "hue_shift": 0.0,
            "temperature": 5600.0,
        },
        "clean-commercial": {
            "description": "Bright, saturated, punchy. Good for product and lifestyle.",
            "lift": (0.03, 0.03, 0.03),
            "gamma": (1.1, 1.1, 1.1),
            "gain": (1.05, 1.05, 1.05),
            "saturation": 1.2,
            "hue_shift": 0.0,
            "temperature": 5600.0,
        },
        "documentary-natural": {
            "description": "Minimal grading, slight contrast boost. Authentic feel.",
            "lift": (0.0, 0.0, 0.0),
            "gamma": (0.95, 0.95, 0.95),
            "gain": (1.02, 1.02, 1.02),
            "saturation": 1.0,
            "hue_shift": 0.0,
            "temperature": 5600.0,
        },
        "social-vibrant": {
            "description": "High saturation, lifted shadows. Optimized for social media.",
            "lift": (0.05, 0.05, 0.05),
            "gamma": (1.15, 1.15, 1.15),
            "gain": (1.0, 1.0, 1.0),
            "saturation": 1.3,
            "hue_shift": 0.0,
            "temperature": 5600.0,
        },
        "film-noir": {
            "description": "High contrast, desaturated. Classic noir aesthetic.",
            "lift": (-0.02, -0.02, -0.02),
            "gamma": (0.8, 0.8, 0.8),
            "gain": (0.95, 0.95, 0.95),
            "saturation": 0.3,
            "hue_shift": 0.0,
            "temperature": 5600.0,
        },
        "warm-golden": {
            "description": "Warm golden hour feel. Good for lifestyle and travel.",
            "lift": (0.0, 0.0, 0.0),
            "gamma": (1.05, 1.0, 0.9),
            "gain": (1.0, 1.0, 1.0),
            "saturation": 1.1,
            "hue_shift": 0.0,
            "temperature": 4500.0,
        },
        "cool-blue": {
            "description": "Cool blue tone. Good for tech, sci-fi, corporate.",
            "lift": (0.0, 0.0, 0.0),
            "gamma": (0.95, 1.0, 1.1),
            "gain": (1.0, 1.0, 1.0),
            "saturation": 0.9,
            "hue_shift": 0.0,
            "temperature": 7500.0,
        },
        "bleach-bypass": {
            "description": "High contrast, desaturated midtones. Gritty film look.",
            "lift": (0.0, 0.0, 0.0),
            "gamma": (0.85, 0.85, 0.85),
            "gain": (1.1, 1.1, 1.1),
            "saturation": 0.5,
            "hue_shift": 0.0,
            "temperature": 5600.0,
        },
    }

    @classmethod
    def list_presets(cls) -> List[Dict[str, str]]:
        """Return list of preset names and descriptions."""
        return [{"name": name, "description": p["description"]}
                for name, p in cls.PRESETS.items()]

    @classmethod
    def get_preset(cls, name: str) -> Dict[str, Any]:
        """Get preset parameters by name.

        Raises:
            InvalidParameterError: If preset name not found.
        """
        if name not in cls.PRESETS:
            available = ", ".join(cls.PRESETS.keys())
            raise InvalidParameterError(
                f"Unknown look preset '{name}'. Available: {available}")
        return cls.PRESETS[name]


class ReferenceBank:
    """Manage a bank of approved reference frames for shot matching.

    Reference frames are stored at tools/color_grader_refs/ with an
    index.json metadata file.
    """

    DEFAULT_DIR = Path("{{CATALYST_ROOT}}/tools/color_grader_refs")

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else self.DEFAULT_DIR
        self.index_path = self.base_dir / "index.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create reference bank directory if it doesn't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> List[Dict[str, Any]]:
        """Load the index file."""
        if not self.index_path.exists():
            return []
        with open(self.index_path, 'r') as f:
            return json.load(f)

    def _save_index(self, index: List[Dict[str, Any]]) -> None:
        """Save the index file."""
        with open(self.index_path, 'w') as f:
            json.dump(index, f, indent=2)

    def add(self, image_path: str, name: str,
            tags: Optional[List[str]] = None,
            notes: str = "") -> Dict[str, Any]:
        """Add a reference frame to the bank.

        Args:
            image_path: Path to the reference image file.
            name: Human-readable name for the reference.
            tags: Optional list of tags for searching.
            notes: Optional notes about the reference.

        Returns:
            Metadata entry for the added reference.
        """
        src = Path(image_path)
        if not src.exists():
            raise FileNotFoundError_(f"Image not found: {image_path}")

        # Generate unique filename
        file_hash = hashlib.md5(src.read_bytes()).hexdigest()[:8]
        dest_name = f"{name.replace(' ', '_')}_{file_hash}{src.suffix}"
        dest = self.base_dir / dest_name

        # Copy file
        import shutil
        shutil.copy2(str(src), str(dest))

        entry = {
            "name": name,
            "filename": dest_name,
            "path": str(dest),
            "original_path": str(src),
            "tags": tags or [],
            "notes": notes,
            "date_added": datetime.now().isoformat(),
        }

        index = self._load_index()
        # Remove existing entry with same name
        index = [e for e in index if e["name"] != name]
        index.append(entry)
        self._save_index(index)

        return entry

    def list_refs(self) -> List[Dict[str, Any]]:
        """List all references in the bank."""
        return self._load_index()

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a reference by name."""
        index = self._load_index()
        for entry in index:
            if entry["name"] == name:
                return entry
        return None


class GradingPipeline:
    """Full automated grading pipeline.

    Runs a structured workflow of correction steps, applying each as a
    LUT to the frame using OpenCV (no DaVinci Resolve dependency).

    Workflows:
        - full: All 7 steps (exposure, white balance, contrast, saturation,
                skin tones, creative look, shot matching)
        - primary-only: Steps 1-4
        - match-only: Step 7 only
    """

    def __init__(self, max_iterations: int = 10, threshold: int = 85):
        self.max_iterations = max_iterations
        self.threshold = threshold
        self.grader = ColorGrader()
        self.evaluator = QualityEvaluator()

    def grade(self,
              frame: np.ndarray,
              reference: Optional[np.ndarray] = None,
              workflow: str = "full",
              look: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """Run the grading pipeline on a frame.

        Args:
            frame: BGR input frame (uint8).
            reference: Optional BGR reference frame for shot matching.
            workflow: 'full', 'primary-only', or 'match-only'.
            look: Optional creative look preset name.

        Returns:
            Tuple of (graded_frame, combined_lut, report_dict).
        """
        report: Dict[str, Any] = {
            "workflow": workflow,
            "iterations": [],
            "steps_applied": [],
        }

        # Initialize combined LUT as identity
        size = 33
        combined_cube = self.grader.generate_identity_cube(size)
        current_frame = frame.copy()

        if workflow == "match-only":
            steps = [("shot_matching", {})]
        elif workflow == "primary-only":
            steps = [
                ("exposure", {}),
                ("white_balance", {}),
                ("contrast", {}),
                ("saturation_adj", {}),
            ]
        else:  # full
            steps = [
                ("exposure", {}),
                ("white_balance", {}),
                ("contrast", {}),
                ("saturation_adj", {}),
                ("skin_tones", {}),
                ("creative_look", {"look": look}),
                ("shot_matching", {}),
            ]

        for step_name, step_kwargs in steps:
            step_cube = self._run_step(step_name, current_frame,
                                       reference=reference, **step_kwargs)
            if step_cube is not None:
                # Apply step LUT to the current frame
                current_frame = self.grader.apply_lut_to_frame(
                    current_frame, step_cube, size)
                # Chain the LUTs: apply step transform to combined cube
                combined_cube = self._chain_cubes(combined_cube, step_cube, size)
                report["steps_applied"].append(step_name)

        # Iterative refinement
        for iteration in range(self.max_iterations):
            eval_result = self.evaluator.evaluate(current_frame)
            score = eval_result["overall_score"]
            report["iterations"].append({
                "iteration": iteration + 1,
                "score": score,
                "pass": eval_result["overall_pass"],
            })

            if score >= self.threshold:
                report["final_score"] = score
                report["converged"] = True
                break

            # Analyze failures and apply targeted corrections
            correction_cube = self._targeted_correction(current_frame, eval_result, size)
            if correction_cube is not None:
                current_frame = self.grader.apply_lut_to_frame(
                    current_frame, correction_cube, size)
                combined_cube = self._chain_cubes(combined_cube, correction_cube, size)
        else:
            eval_result = self.evaluator.evaluate(current_frame)
            report["final_score"] = eval_result["overall_score"]
            report["converged"] = False

        return current_frame, combined_cube, report

    def _run_step(self, step_name: str, frame: np.ndarray,
                  reference: Optional[np.ndarray] = None,
                  look: Optional[str] = None,
                  **kwargs: Any) -> Optional[np.ndarray]:
        """Run a single grading step and return a LUT cube."""
        size = 33

        if step_name == "exposure":
            return self._correct_exposure(frame, size)

        elif step_name == "white_balance":
            return self._correct_white_balance(frame, size)

        elif step_name == "contrast":
            return self._correct_contrast(frame, size)

        elif step_name == "saturation_adj":
            return self._correct_saturation(frame, size)

        elif step_name == "skin_tones":
            return self._correct_skin_tones(frame, size)

        elif step_name == "creative_look":
            if look:
                preset = LookLibrary.get_preset(look)
                return self.grader.generate_lut(
                    lift=preset["lift"],
                    gamma=preset["gamma"],
                    gain=preset["gain"],
                    saturation=preset["saturation"],
                    hue_shift_deg=preset["hue_shift"],
                    temperature=preset["temperature"],
                    size=size,
                )
            return None

        elif step_name == "shot_matching":
            ref = kwargs.get("reference", reference)
            if ref is not None:
                return ShotMatcher.generate_corrective_lut(
                    frame, ref, method="mkl", size=size)
            return None

        return None

    def _correct_exposure(self, frame: np.ndarray, size: int) -> Optional[np.ndarray]:
        """Analyze histogram and adjust gamma to center distribution."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_luma = float(gray.mean()) / 255.0

        # Target: mean luma around 0.45 (slightly below midpoint for natural look)
        target = 0.45
        if abs(mean_luma - target) < 0.03:
            return None  # Close enough

        # Adjust gamma: if too dark, gamma > 1 brightens; if too bright, gamma < 1 darkens
        # Relationship: new_mean ~ old_mean ^ (1/gamma)
        # Solve: target = mean ^ (1/gamma) => gamma = log(mean) / log(target)
        if mean_luma > 0.01:
            gamma_val = math.log(mean_luma) / math.log(target)
            gamma_val = max(0.5, min(2.0, gamma_val))  # Clamp to safe range
        else:
            gamma_val = 2.0  # Very dark, brighten significantly

        return self.grader.generate_lut(
            gamma=(gamma_val, gamma_val, gamma_val), size=size)

    def _correct_white_balance(self, frame: np.ndarray, size: int) -> Optional[np.ndarray]:
        """Detect color cast and generate temperature correction."""
        b, g, r = cv2.split(frame)
        mean_r = float(r.mean())
        mean_g = float(g.mean())
        mean_b = float(b.mean())

        max_diff = max(abs(mean_r - mean_g), abs(mean_g - mean_b),
                       abs(mean_b - mean_r))

        if max_diff < 8.0:
            return None  # Acceptable balance

        # Compute per-channel gamma correction to equalize means
        avg = (mean_r + mean_g + mean_b) / 3.0
        if avg < 1.0:
            return None

        gamma_r = max(0.5, min(2.0, avg / max(mean_r, 1.0)))
        gamma_g = max(0.5, min(2.0, avg / max(mean_g, 1.0)))
        gamma_b = max(0.5, min(2.0, avg / max(mean_b, 1.0)))

        return self.grader.generate_lut(
            gamma=(gamma_r, gamma_g, gamma_b), size=size)

    def _correct_contrast(self, frame: np.ndarray, size: int) -> Optional[np.ndarray]:
        """Analyze tonal range and adjust lift/gain to expand."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sorted_vals = np.sort(gray.ravel())
        n = len(sorted_vals)
        p5 = float(sorted_vals[int(n * 0.05)]) / 255.0
        p95 = float(sorted_vals[int(n * 0.95)]) / 255.0
        contrast_range = (p95 - p5) * 255.0

        if contrast_range > 100:
            return None  # Sufficient contrast

        # Lift shadows down, push gain up
        lift_adj = max(-0.05, -p5 * 0.5)
        gain_adj = min(1.3, 1.0 / max(p95, 0.5))

        return self.grader.generate_lut(
            lift=(lift_adj, lift_adj, lift_adj),
            gain=(gain_adj, gain_adj, gain_adj),
            size=size,
        )

    def _correct_saturation(self, frame: np.ndarray, size: int) -> Optional[np.ndarray]:
        """Analyze mean saturation and adjust to target range."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mean_sat = float(hsv[:, :, 1].mean())

        # Target range: 70-130
        if 60 < mean_sat < 140:
            return None  # Acceptable

        target = 100.0
        factor = target / max(mean_sat, 1.0)
        factor = max(0.3, min(2.0, factor))

        return self.grader.generate_lut(saturation=factor, size=size)

    def _correct_skin_tones(self, frame: np.ndarray, size: int) -> Optional[np.ndarray]:
        """Check skin tone regions and adjust if needed."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)

        skin_mask = ((h >= 0) & (h <= 25) &
                     (s >= 51) & (s <= 204) &
                     (v >= 50) & (v <= 240))

        if float(np.sum(skin_mask)) / float(h.size) < 0.01:
            return None  # No significant skin detected

        skin_hue_mean = float(h[skin_mask].mean())
        # Ideal skin hue in OpenCV: ~10 (= 20 degrees)
        # If too red (< 5) or too yellow (> 20), shift
        if 5 <= skin_hue_mean <= 20:
            return None  # Acceptable

        # Calculate a gentle hue shift
        target_hue = 12.0  # Middle of acceptable range
        shift_needed = (target_hue - skin_hue_mean) * 2.0  # OpenCV to degrees
        shift_needed = max(-10, min(10, shift_needed))  # Limit correction

        return self.grader.generate_lut(hue_shift_deg=shift_needed, size=size)

    def _targeted_correction(self, frame: np.ndarray,
                             eval_result: Dict[str, Any],
                             size: int) -> Optional[np.ndarray]:
        """Apply targeted corrections based on evaluation failures."""
        corrections_needed = []

        if not eval_result["clipping"]["pass"]:
            if eval_result["clipping"]["blacks_pct"] > 2.0:
                corrections_needed.append(("lift", (0.02, 0.02, 0.02)))
            if eval_result["clipping"]["whites_pct"] > 2.0:
                corrections_needed.append(("gain", (0.95, 0.95, 0.95)))

        if not eval_result["color_cast"]["pass"]:
            cube = self._correct_white_balance(frame, size)
            if cube is not None:
                return cube

        if not eval_result["contrast"]["pass"]:
            cube = self._correct_contrast(frame, size)
            if cube is not None:
                return cube

        if not eval_result["saturation"]["pass"]:
            cube = self._correct_saturation(frame, size)
            if cube is not None:
                return cube

        if corrections_needed:
            lift = (0.0, 0.0, 0.0)
            gain = (1.0, 1.0, 1.0)
            for corr_type, corr_val in corrections_needed:
                if corr_type == "lift":
                    lift = corr_val
                elif corr_type == "gain":
                    gain = corr_val
            return self.grader.generate_lut(lift=lift, gain=gain, size=size)

        return None

    def _chain_cubes(self, cube_a: np.ndarray, cube_b: np.ndarray,
                     size: int) -> np.ndarray:
        """Chain two LUT cubes: apply cube_b's transform to cube_a's output.

        This creates a combined LUT where cube_a is applied first, then cube_b.
        """
        # Reshape cube_a values as "input image" to cube_b
        # Each entry in cube_a is an RGB triplet that we pass through cube_b
        lut_b = cube_b.reshape(size, size, size, 3)

        scale = float(size - 1)
        coords = cube_a * scale

        c0 = np.floor(coords).astype(np.int32)
        c1 = np.minimum(c0 + 1, size - 1)
        c0 = np.clip(c0, 0, size - 1)

        frac = coords - c0.astype(np.float64)

        r0, g0, b0 = c0[:, 0], c0[:, 1], c0[:, 2]
        r1, g1, b1 = c1[:, 0], c1[:, 1], c1[:, 2]
        fr = frac[:, 0:1]
        fg = frac[:, 1:2]
        fb = frac[:, 2:3]

        c000 = lut_b[b0, g0, r0]
        c001 = lut_b[b0, g0, r1]
        c010 = lut_b[b0, g1, r0]
        c011 = lut_b[b0, g1, r1]
        c100 = lut_b[b1, g0, r0]
        c101 = lut_b[b1, g0, r1]
        c110 = lut_b[b1, g1, r0]
        c111 = lut_b[b1, g1, r1]

        c00 = c000 * (1 - fr) + c001 * fr
        c01 = c010 * (1 - fr) + c011 * fr
        c10 = c100 * (1 - fr) + c101 * fr
        c11 = c110 * (1 - fr) + c111 * fr

        c0_ = c00 * (1 - fg) + c01 * fg
        c1_ = c10 * (1 - fg) + c11 * fg

        result = c0_ * (1 - fb) + c1_ * fb
        return np.clip(result, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Layer 4: Output Formatting
# ---------------------------------------------------------------------------

def format_output(data: Any, use_json: bool = False) -> str:
    """Format output for display.

    Args:
        data: Data to format (dict, list, or string).
        use_json: If True, output as JSON. Otherwise human-readable.

    Returns:
        Formatted string.
    """
    if use_json:
        return json.dumps(data, indent=2, default=str)

    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"\n  {BOLD}{key}{RESET}:")
                for k2, v2 in value.items():
                    if k2 == "pass":
                        indicator = f"{GREEN}PASS{RESET}" if v2 else f"{RED}FAIL{RESET}"
                        lines.append(f"    {k2}: {indicator}")
                    else:
                        lines.append(f"    {k2}: {v2}")
            elif key == "overall_pass":
                indicator = f"{GREEN}PASS{RESET}" if value else f"{RED}FAIL{RESET}"
                lines.append(f"\n  {BOLD}Overall: {indicator}")
            elif key == "overall_score":
                color = GREEN if value >= 85 else YELLOW if value >= 70 else RED
                lines.append(f"  {BOLD}Score: {color}{value}/100{RESET}")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    if isinstance(data, list):
        return "\n".join(str(item) for item in data)

    return str(data)


# ---------------------------------------------------------------------------
# Helper: Parse comma-separated float triple
# ---------------------------------------------------------------------------

def parse_triple(value: str, name: str = "value") -> Tuple[float, float, float]:
    """Parse a comma-separated triple of floats.

    Args:
        value: String like '0.02,0.0,-0.03'.
        name: Parameter name for error messages.

    Returns:
        Tuple of three floats.

    Raises:
        InvalidParameterError: If parsing fails.
    """
    try:
        parts = [float(x.strip()) for x in value.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Expected 3 values, got {len(parts)}")
        return (parts[0], parts[1], parts[2])
    except (ValueError, TypeError) as e:
        raise InvalidParameterError(
            f"Invalid {name} '{value}': expected R,G,B format (e.g., 1.0,1.0,1.0). "
            f"Error: {e}")


def load_frame(path: str) -> np.ndarray:
    """Load an image file as a BGR numpy array.

    Args:
        path: Path to the image file.

    Returns:
        BGR image as uint8 numpy array.

    Raises:
        FileNotFoundError_: If file doesn't exist.
        ProcessingError: If OpenCV can't read the file.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError_(
            f"File not found: {path}\n"
            f"  Hint: Use an absolute path or check the filename.")

    frame = cv2.imread(str(p))
    if frame is None:
        raise ProcessingError(
            f"Could not read image: {path}\n"
            f"  Hint: Ensure it's a valid image file (PNG, JPG, TIFF, EXR).")

    return frame


# ---------------------------------------------------------------------------
# Layer 2: Handler Functions
# ---------------------------------------------------------------------------

def cmd_generate_lut(args: argparse.Namespace) -> int:
    """Handle the generate-lut subcommand."""
    grader = ColorGrader()

    # Check if a named look preset is requested
    if args.look:
        preset = LookLibrary.get_preset(args.look)
        lift = preset["lift"]
        gamma = preset["gamma"]
        gain = preset["gain"]
        saturation = preset["saturation"]
        hue_shift = preset["hue_shift"]
        temperature = preset["temperature"]
        title = f"Huxley - {args.look}"
    else:
        lift = parse_triple(args.lift, "lift") if args.lift else (0.0, 0.0, 0.0)
        gamma = parse_triple(args.gamma, "gamma") if args.gamma else (1.0, 1.0, 1.0)
        gain = parse_triple(args.gain, "gain") if args.gain else (1.0, 1.0, 1.0)
        saturation = args.saturation
        hue_shift = args.hue_shift
        temperature = args.temperature
        title = "Huxley Custom Grade"

    cube = grader.generate_lut(
        lift=lift,
        gamma=gamma,
        gain=gain,
        saturation=saturation,
        hue_shift_deg=hue_shift,
        temperature=temperature,
        size=args.size,
    )

    output = args.output or "output.cube"
    grader.write_cube_file(cube, output, title=title, size=args.size)

    result = {
        "status": "success",
        "output": str(Path(output).resolve()),
        "size": args.size,
        "entries": args.size ** 3,
        "parameters": {
            "lift": list(lift),
            "gamma": list(gamma),
            "gain": list(gain),
            "saturation": saturation,
            "hue_shift": hue_shift,
            "temperature": temperature,
        },
    }

    if args.look:
        result["look"] = args.look

    print(format_output(result, args.json))
    return 0


def cmd_cdl(args: argparse.Namespace) -> int:
    """Handle the cdl subcommand."""
    grader = ColorGrader()

    slope = parse_triple(args.slope, "slope") if args.slope else (1.0, 1.0, 1.0)
    offset = parse_triple(args.offset, "offset") if args.offset else (0.0, 0.0, 0.0)
    power = parse_triple(args.power, "power") if args.power else (1.0, 1.0, 1.0)
    saturation = args.saturation

    output = args.output or "output.cube"
    fmt = args.format if hasattr(args, "format") and args.format else None

    if fmt == "cdl" or (output.endswith(".cdl")):
        # Write as CDL XML
        grader.write_cdl_xml(slope, offset, power, saturation, output)
        result = {
            "status": "success",
            "format": "cdl",
            "output": str(Path(output).resolve()),
            "parameters": {
                "slope": list(slope),
                "offset": list(offset),
                "power": list(power),
                "saturation": saturation,
            },
        }
    else:
        # Generate as .cube LUT
        size = args.size if hasattr(args, "size") else 33
        cube = grader.generate_cdl_lut(slope, offset, power, saturation, size=size)
        grader.write_cube_file(cube, output, title="Huxley CDL Grade", size=size)
        result = {
            "status": "success",
            "format": "cube",
            "output": str(Path(output).resolve()),
            "size": size,
            "entries": size ** 3,
            "parameters": {
                "slope": list(slope),
                "offset": list(offset),
                "power": list(power),
                "saturation": saturation,
            },
        }

    print(format_output(result, args.json))
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Handle the evaluate subcommand."""
    frame = load_frame(args.frame)

    reference = None
    if args.reference:
        reference = load_frame(args.reference)

    previous_frame = None
    if hasattr(args, "previous_frame") and args.previous_frame:
        previous_frame = load_frame(args.previous_frame)

    ai_eval = hasattr(args, "ai") and args.ai

    evaluator = QualityEvaluator()
    results = evaluator.evaluate(frame, reference=reference,
                                 previous_frame=previous_frame,
                                 ai_eval=ai_eval)

    print(format_output(results, args.json))
    return 0


def cmd_scopes(args: argparse.Namespace) -> int:
    """Handle the scopes subcommand."""
    frame = load_frame(args.frame)

    scope_types = [t.strip() for t in args.types.split(",")]
    valid_types = {"waveform", "vectorscope", "parade", "histogram"}
    for t in scope_types:
        if t not in valid_types:
            print(f"{RED}Unknown scope type: {t}{RESET}")
            print(f"  Available: {', '.join(sorted(valid_types))}")
            return 1

    output_dir = Path(args.output_dir or ".")
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = ScopeGenerator()
    outputs = []

    for scope_type in scope_types:
        if scope_type == "waveform":
            img = generator.generate_waveform(frame)
        elif scope_type == "vectorscope":
            img = generator.generate_vectorscope(frame)
        elif scope_type == "parade":
            img = generator.generate_parade(frame)
        elif scope_type == "histogram":
            img = generator.generate_histogram(frame)
        else:
            continue

        output_path = output_dir / f"{scope_type}.png"
        cv2.imwrite(str(output_path), img)
        outputs.append({
            "type": scope_type,
            "path": str(output_path.resolve()),
            "dimensions": f"{img.shape[1]}x{img.shape[0]}",
        })

    result = {
        "status": "success",
        "scopes_generated": len(outputs),
        "output_dir": str(output_dir.resolve()),
        "files": outputs,
    }

    print(format_output(result, args.json))
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    """Handle the match subcommand."""
    source = load_frame(args.source)
    reference = load_frame(args.reference)

    method = args.method or "mkl"
    valid_methods = ["mkl", "reinhard", "hm-mvgd-hm"]
    if method not in valid_methods:
        print(f"{RED}Unknown matching method: {method}{RESET}")
        print(f"  Available: {', '.join(valid_methods)}")
        return 1

    output = args.output or "corrective.cube"
    size = args.size if hasattr(args, "size") else 33

    # Generate corrective LUT
    cube = ShotMatcher.generate_corrective_lut(
        source, reference, method=method, size=size)

    ColorGrader.write_cube_file(
        cube, output,
        title=f"Huxley Shot Match ({method})",
        size=size,
    )

    # Also save the matched frame if requested
    matched_frame_path = None
    if hasattr(args, "output_frame") and args.output_frame:
        matched = ShotMatcher.match(source, reference, method=method)
        cv2.imwrite(args.output_frame, matched)
        matched_frame_path = str(Path(args.output_frame).resolve())

    result = {
        "status": "success",
        "method": method,
        "output_lut": str(Path(output).resolve()),
        "size": size,
        "entries": size ** 3,
    }
    if matched_frame_path:
        result["output_frame"] = matched_frame_path

    print(format_output(result, args.json))
    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    """Handle the grade subcommand."""
    frame = load_frame(args.frame)

    reference = None
    if args.reference:
        reference = load_frame(args.reference)

    workflow = args.workflow or "full"
    valid_workflows = ["full", "primary-only", "match-only"]
    if workflow not in valid_workflows:
        print(f"{RED}Unknown workflow: {workflow}{RESET}")
        print(f"  Available: {', '.join(valid_workflows)}")
        return 1

    max_iter = args.max_iterations if hasattr(args, "max_iterations") else 10
    threshold = args.threshold if hasattr(args, "threshold") else 85
    look = args.look if hasattr(args, "look") else None

    pipeline = GradingPipeline(max_iterations=max_iter, threshold=threshold)
    graded_frame, combined_cube, report = pipeline.grade(
        frame, reference=reference, workflow=workflow, look=look)

    # Write output LUT
    output_lut = args.output or "graded.cube"
    ColorGrader.write_cube_file(
        combined_cube, output_lut,
        title=f"Huxley Auto Grade ({workflow})",
        size=33,
    )

    # Write graded frame
    output_frame = None
    if hasattr(args, "output_frame") and args.output_frame:
        cv2.imwrite(args.output_frame, graded_frame)
        output_frame = str(Path(args.output_frame).resolve())

    result = {
        "status": "success",
        "workflow": workflow,
        "output_lut": str(Path(output_lut).resolve()),
        "steps_applied": report["steps_applied"],
        "iterations": len(report["iterations"]),
        "final_score": report.get("final_score", 0),
        "converged": report.get("converged", False),
        "iteration_scores": [it["score"] for it in report["iterations"]],
    }
    if output_frame:
        result["output_frame"] = output_frame
    if look:
        result["creative_look"] = look

    print(format_output(result, args.json))
    return 0


def cmd_looks_list(args: argparse.Namespace) -> int:
    """Handle the looks list subcommand."""
    presets = LookLibrary.list_presets()

    if args.json:
        print(json.dumps(presets, indent=2))
    else:
        print(f"\n{BOLD}Available Creative Looks:{RESET}\n")
        for p in presets:
            print(f"  {CYAN}{p['name']}{RESET}")
            print(f"    {DIM}{p['description']}{RESET}")
        print()

    return 0


def cmd_looks_preview(args: argparse.Namespace) -> int:
    """Handle the looks preview subcommand."""
    look_name = args.look_name
    preset = LookLibrary.get_preset(look_name)

    if not args.frame:
        # Just show parameters
        result = {
            "name": look_name,
            "description": preset["description"],
            "parameters": {
                "lift": list(preset["lift"]),
                "gamma": list(preset["gamma"]),
                "gain": list(preset["gain"]),
                "saturation": preset["saturation"],
                "hue_shift": preset["hue_shift"],
                "temperature": preset["temperature"],
            },
        }
        print(format_output(result, args.json))
        return 0

    # Apply look to frame and save preview
    frame = load_frame(args.frame)
    grader = ColorGrader()

    cube = grader.generate_lut(
        lift=preset["lift"],
        gamma=preset["gamma"],
        gain=preset["gain"],
        saturation=preset["saturation"],
        hue_shift_deg=preset["hue_shift"],
        temperature=preset["temperature"],
        size=33,
    )

    graded = grader.apply_lut_to_frame(frame, cube, 33)

    output = args.output or f"preview_{look_name}.png"
    cv2.imwrite(output, graded)

    result = {
        "status": "success",
        "look": look_name,
        "output": str(Path(output).resolve()),
    }

    print(format_output(result, args.json))
    return 0


def cmd_refs_add(args: argparse.Namespace) -> int:
    """Handle the refs add subcommand."""
    tags = []
    if hasattr(args, "tags") and args.tags:
        tags = [t.strip() for t in args.tags.split(",")]

    bank = ReferenceBank()
    entry = bank.add(args.image, args.name, tags=tags,
                     notes=args.notes if hasattr(args, "notes") else "")

    result = {
        "status": "success",
        "action": "added",
        "entry": entry,
    }
    print(format_output(result, args.json))
    return 0


def cmd_refs_list(args: argparse.Namespace) -> int:
    """Handle the refs list subcommand."""
    bank = ReferenceBank()
    refs = bank.list_refs()

    if args.json:
        print(json.dumps(refs, indent=2))
    else:
        if not refs:
            print(f"\n{DIM}No references in bank.{RESET}")
            print(f"  Add one: python3 tools/color_grader.py refs add "
                  f"frame.png --name hero-shot\n")
        else:
            print(f"\n{BOLD}Reference Bank ({len(refs)} frames):{RESET}\n")
            for ref in refs:
                tags = ", ".join(ref.get("tags", []))
                print(f"  {CYAN}{ref['name']}{RESET}")
                print(f"    Path: {ref['path']}")
                if tags:
                    print(f"    Tags: {tags}")
                print(f"    Added: {ref['date_added']}")
            print()

    return 0


def cmd_refs_show(args: argparse.Namespace) -> int:
    """Handle the refs show subcommand."""
    bank = ReferenceBank()
    ref = bank.get(args.name)

    if ref is None:
        print(f"{RED}Reference not found: {args.name}{RESET}")
        print(f"  Use 'refs list' to see available references.")
        return 1

    print(format_output(ref, args.json))
    return 0


# ---------------------------------------------------------------------------
# Layer 1: CLI Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for all subcommands."""
    # Shared parent for global flags (inherited by all subcommands)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="Output in machine-readable JSON format")
    common.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging to stderr")

    parser = argparse.ArgumentParser(
        prog="color_grader",
        description=(
            "Programmatic color grading CLI for Huxley Studio Engineer.\n"
            "Generate LUTs, evaluate frames, create scopes, match shots, "
            "and run automated grading pipelines."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog=(
            "Examples:\n"
            "  %(prog)s generate-lut --lift 0.02,0.0,-0.03 "
            "--gamma 1.0,0.95,0.9 --output warm.cube\n"
            "  %(prog)s evaluate --frame shot.png --json\n"
            "  %(prog)s scopes --frame shot.png --types waveform,vectorscope\n"
            "  %(prog)s match --source shot.png --reference hero.png\n"
            "  %(prog)s grade --frame shot.png --workflow full --threshold 85\n"
            "  %(prog)s looks list\n"
            "  %(prog)s refs add hero.png --name hero-shot --tags outdoor,warm\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- generate-lut ---
    p_gen = subparsers.add_parser(
        "generate-lut", parents=[common],
        help="Generate a .cube LUT from lift/gamma/gain parameters",
    )
    p_gen.add_argument("--lift", help="R,G,B lift values (e.g., 0.02,0.0,-0.03)")
    p_gen.add_argument("--gamma", help="R,G,B gamma values (e.g., 1.0,0.95,0.9)")
    p_gen.add_argument("--gain", help="R,G,B gain values (e.g., 1.05,1.0,0.98)")
    p_gen.add_argument("--saturation", type=float, default=1.0,
                        help="Saturation factor (default: 1.0)")
    p_gen.add_argument("--hue-shift", type=float, default=0.0,
                        help="Hue shift in degrees (default: 0)")
    p_gen.add_argument("--temperature", type=float, default=5600.0,
                        help="Color temperature in Kelvin (default: 5600)")
    p_gen.add_argument("--size", type=int, default=33, choices=[17, 33, 64],
                        help="LUT cube dimension (default: 33)")
    p_gen.add_argument("--output", "-o", help="Output .cube file path")
    p_gen.add_argument("--look", help="Use a named preset (e.g., cinematic-teal-orange)")

    # --- cdl ---
    p_cdl = subparsers.add_parser(
        "cdl", parents=[common],
        help="Generate CDL (Color Decision List) as .cube or .cdl file",
    )
    p_cdl.add_argument("--slope", help="R,G,B slope values (e.g., 1.1,1.0,0.95)")
    p_cdl.add_argument("--offset", help="R,G,B offset values (e.g., 0.02,0.0,-0.01)")
    p_cdl.add_argument("--power", help="R,G,B power values (e.g., 1.0,1.0,1.05)")
    p_cdl.add_argument("--saturation", type=float, default=1.0,
                        help="Saturation factor (default: 1.0)")
    p_cdl.add_argument("--size", type=int, default=33, choices=[17, 33, 64],
                        help="LUT cube dimension (default: 33)")
    p_cdl.add_argument("--output", "-o", help="Output file path (.cube or .cdl)")
    p_cdl.add_argument("--format", choices=["cube", "cdl"],
                        help="Output format (auto-detected from extension)")

    # --- evaluate ---
    p_eval = subparsers.add_parser(
        "evaluate", parents=[common],
        help="Evaluate frame color quality with objective metrics",
    )
    p_eval.add_argument("--frame", required=True, help="Path to frame image")
    p_eval.add_argument("--reference", help="Path to reference image for comparison")
    p_eval.add_argument("--previous-frame",
                         help="Path to previous frame for temporal consistency check")
    p_eval.add_argument("--ai", action="store_true",
                         help="Enable AI vision evaluation (requires GEMINI_API_KEY)")

    # --- scopes ---
    p_scopes = subparsers.add_parser(
        "scopes", parents=[common],
        help="Generate scope visualizations (waveform, vectorscope, parade, histogram)",
    )
    p_scopes.add_argument("--frame", required=True, help="Path to frame image")
    p_scopes.add_argument("--types", default="waveform,vectorscope,parade,histogram",
                           help="Comma-separated scope types (default: all)")
    p_scopes.add_argument("--output-dir", help="Output directory for scope images")

    # --- match ---
    p_match = subparsers.add_parser(
        "match", parents=[common],
        help="Match shot colors to a reference frame",
    )
    p_match.add_argument("--source", required=True, help="Path to source image")
    p_match.add_argument("--reference", required=True, help="Path to reference image")
    p_match.add_argument("--method", default="mkl",
                          choices=["mkl", "reinhard", "hm-mvgd-hm"],
                          help="Matching algorithm (default: mkl)")
    p_match.add_argument("--size", type=int, default=33, choices=[17, 33, 64],
                          help="LUT cube dimension (default: 33)")
    p_match.add_argument("--output", "-o", help="Output .cube file path")
    p_match.add_argument("--output-frame",
                          help="Also save the matched frame to this path")

    # --- grade ---
    p_grade = subparsers.add_parser(
        "grade", parents=[common],
        help="Run full automated grading pipeline",
    )
    p_grade.add_argument("--frame", required=True, help="Path to frame image")
    p_grade.add_argument("--reference", help="Path to reference image for shot matching")
    p_grade.add_argument("--workflow", default="full",
                          choices=["full", "primary-only", "match-only"],
                          help="Grading workflow (default: full)")
    p_grade.add_argument("--max-iterations", type=int, default=10,
                          help="Maximum refinement iterations (default: 10)")
    p_grade.add_argument("--threshold", type=int, default=85,
                          help="Quality threshold to stop iteration (default: 85)")
    p_grade.add_argument("--output", "-o", help="Output .cube LUT file path")
    p_grade.add_argument("--output-frame", help="Save the graded frame to this path")
    p_grade.add_argument("--look",
                          help="Apply creative look preset (e.g., cinematic-teal-orange)")

    # --- looks ---
    p_looks = subparsers.add_parser(
        "looks", parents=[common],
        help="Creative look presets",
    )
    looks_sub = p_looks.add_subparsers(dest="looks_command")

    looks_sub.add_parser("list", parents=[common],
                         help="List available creative look presets")

    p_lp = looks_sub.add_parser("preview", parents=[common],
                                help="Preview a look preset on a frame")
    p_lp.add_argument("look_name", help="Preset name (e.g., cinematic-teal-orange)")
    p_lp.add_argument("--frame", help="Path to frame image for preview")
    p_lp.add_argument("--output", "-o", help="Output preview image path")

    # --- refs ---
    p_refs = subparsers.add_parser(
        "refs", parents=[common],
        help="Reference bank management",
    )
    refs_sub = p_refs.add_subparsers(dest="refs_command")

    p_ra = refs_sub.add_parser("add", parents=[common],
                               help="Add a reference frame to the bank")
    p_ra.add_argument("image", help="Path to reference image")
    p_ra.add_argument("--name", required=True, help="Reference name")
    p_ra.add_argument("--tags", help="Comma-separated tags (e.g., outdoor,warm,golden-hour)")
    p_ra.add_argument("--notes", default="", help="Notes about the reference")

    refs_sub.add_parser("list", parents=[common],
                        help="List all reference frames")

    p_rs = refs_sub.add_parser("show", parents=[common],
                               help="Show details of a reference frame")
    p_rs.add_argument("name", help="Reference name to show")

    return parser


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

LOOKS_COMMANDS = {
    "list": cmd_looks_list,
    "preview": cmd_looks_preview,
}

REFS_COMMANDS = {
    "add": cmd_refs_add,
    "list": cmd_refs_list,
    "show": cmd_refs_show,
}

TOP_COMMANDS = {
    "generate-lut": cmd_generate_lut,
    "cdl": cmd_cdl,
    "evaluate": cmd_evaluate,
    "scopes": cmd_scopes,
    "match": cmd_match,
    "grade": cmd_grade,
}

NESTED_DISPATCH = {
    "looks": ("looks_command", LOOKS_COMMANDS),
    "refs": ("refs_command", REFS_COMMANDS),
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    # Resolve the command handler
    handler = None

    # Check top-level commands
    if args.command in TOP_COMMANDS:
        handler = TOP_COMMANDS[args.command]

    # Check nested commands
    elif args.command in NESTED_DISPATCH:
        sub_attr, cmd_table = NESTED_DISPATCH[args.command]
        sub_cmd = getattr(args, sub_attr, None)
        if not sub_cmd:
            parser.parse_args([args.command, "--help"])
            return 1
        handler = cmd_table.get(sub_cmd)

    if not handler:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except InvalidParameterError as e:
        print(f"\n{RED}Invalid parameter:{RESET} {e}", file=sys.stderr)
        return 1
    except FileNotFoundError_ as e:
        print(f"\n{RED}File not found:{RESET} {e}", file=sys.stderr)
        return 1
    except ProcessingError as e:
        print(f"\n{RED}Processing error:{RESET} {e}", file=sys.stderr)
        return 1
    except ColorGraderError as e:
        print(f"\n{RED}Error:{RESET} {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}", file=sys.stderr)
        return 130
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n{RED}Unexpected error:{RESET} {e}", file=sys.stderr)
        print(f"{DIM}Use --verbose for detailed traceback.{RESET}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
