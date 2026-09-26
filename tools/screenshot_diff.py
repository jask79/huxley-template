#!/usr/bin/env python3
"""
Screenshot Diffing Tool for iOS Visual Regression Testing
Compares two screenshots and generates a visual diff highlighting changes
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter
    import numpy as np
except ImportError:
    print("Error: Required dependencies not installed")
    print("Install with: pip3 install Pillow numpy")
    sys.exit(1)


class ScreenshotDiffer:
    """Compare screenshots and generate visual diff reports"""

    def __init__(self, threshold: float = 0.01, ignore_antialiasing: bool = True):
        """
        Initialize screenshot differ

        Args:
            threshold: Pixel difference threshold (0.0 to 1.0)
            ignore_antialiasing: Ignore minor antialiasing differences
        """
        self.threshold = threshold
        self.ignore_antialiasing = ignore_antialiasing

    def compare_screenshots(
        self,
        baseline_path: str,
        current_path: str,
        output_dir: Optional[str] = None,
        output_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Compare two screenshots and generate diff

        Args:
            baseline_path: Path to baseline screenshot
            current_path: Path to current screenshot
            output_dir: Directory to save diff images (optional)
            output_format: Output format (json, html, markdown)

        Returns:
            Comparison result dictionary
        """
        # Load images
        try:
            baseline = Image.open(baseline_path).convert("RGB")
            current = Image.open(current_path).convert("RGB")
        except FileNotFoundError as e:
            return {
                "status": "error",
                "message": f"File not found: {e}",
                "match": False
            }

        # Check dimensions
        if baseline.size != current.size:
            return {
                "status": "error",
                "message": f"Image dimensions don't match: {baseline.size} vs {current.size}",
                "match": False,
                "baseline_size": baseline.size,
                "current_size": current.size
            }

        # Calculate differences
        diff_stats = self._calculate_diff(baseline, current)

        # Determine if images match
        match = diff_stats["difference_percentage"] < self.threshold * 100

        result = {
            "status": "success",
            "match": match,
            "baseline": baseline_path,
            "current": current_path,
            "dimensions": baseline.size,
            "difference_percentage": diff_stats["difference_percentage"],
            "pixel_differences": diff_stats["pixel_differences"],
            "total_pixels": diff_stats["total_pixels"],
            "threshold": self.threshold * 100
        }

        # Generate diff images if requested
        if output_dir and not match:
            os.makedirs(output_dir, exist_ok=True)
            diff_images = self._generate_diff_images(baseline, current, diff_stats)

            # Save diff images
            diff_path = os.path.join(output_dir, "diff.png")
            side_by_side_path = os.path.join(output_dir, "side-by-side.png")
            overlay_path = os.path.join(output_dir, "overlay.png")

            diff_images["diff"].save(diff_path)
            diff_images["side_by_side"].save(side_by_side_path)
            diff_images["overlay"].save(overlay_path)

            result["diff_images"] = {
                "diff": diff_path,
                "side_by_side": side_by_side_path,
                "overlay": overlay_path
            }

        return result

    def _calculate_diff(self, baseline: Image.Image, current: Image.Image) -> Dict[str, Any]:
        """Calculate pixel-level differences between images"""
        # Convert to numpy arrays for faster comparison
        baseline_array = np.array(baseline)
        current_array = np.array(current)

        # Calculate absolute difference
        diff_array = np.abs(baseline_array.astype(int) - current_array.astype(int))

        # Apply threshold for antialiasing
        if self.ignore_antialiasing:
            # Ignore differences less than 5 (out of 255)
            diff_array[diff_array < 5] = 0

        # Count different pixels
        pixel_differences = np.sum(np.any(diff_array > 0, axis=2))
        total_pixels = baseline_array.shape[0] * baseline_array.shape[1]
        difference_percentage = (pixel_differences / total_pixels) * 100

        return {
            "pixel_differences": int(pixel_differences),
            "total_pixels": int(total_pixels),
            "difference_percentage": float(difference_percentage),
            "diff_array": diff_array
        }

    def _generate_diff_images(
        self,
        baseline: Image.Image,
        current: Image.Image,
        diff_stats: Dict[str, Any]
    ) -> Dict[str, Image.Image]:
        """Generate visual diff representations"""
        width, height = baseline.size

        # 1. Diff image (red highlights)
        diff_image = Image.new("RGB", (width, height), "black")
        diff_array = diff_stats["diff_array"]

        # Create red highlight for differences
        highlight = np.zeros_like(diff_array)
        highlight[np.any(diff_array > 0, axis=2)] = [255, 0, 0]  # Red
        diff_image = Image.fromarray(highlight.astype(np.uint8))

        # Blend with current image
        diff_image = Image.blend(current, diff_image, 0.5)

        # 2. Side-by-side comparison
        side_by_side = Image.new("RGB", (width * 2 + 20, height + 60), "white")

        # Add labels
        draw = ImageDraw.Draw(side_by_side)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        except:
            font = ImageFont.load_default()

        draw.text((10, 10), "Baseline", fill="black", font=font)
        draw.text((width + 30, 10), "Current", fill="black", font=font)

        # Paste images
        side_by_side.paste(baseline, (0, 40))
        side_by_side.paste(current, (width + 20, 40))

        # Draw separator line
        draw.line([(width + 10, 0), (width + 10, height + 60)], fill="gray", width=2)

        # 3. Overlay comparison (with slider effect)
        overlay = current.copy()
        overlay_draw = ImageDraw.Draw(overlay, "RGBA")

        # Draw difference regions as semi-transparent red
        diff_mask = np.any(diff_array > 0, axis=2)
        overlay_array = np.array(overlay)
        overlay_array[diff_mask] = [255, 0, 0]  # Red overlay

        overlay = Image.fromarray(overlay_array)
        overlay = Image.blend(current, overlay, 0.3)

        return {
            "diff": diff_image,
            "side_by_side": side_by_side,
            "overlay": overlay
        }

    def batch_compare(
        self,
        baseline_dir: str,
        current_dir: str,
        output_dir: str,
        pattern: str = "*.png"
    ) -> Dict[str, Any]:
        """
        Compare all screenshots in two directories

        Args:
            baseline_dir: Directory with baseline screenshots
            current_dir: Directory with current screenshots
            output_dir: Directory to save diff reports
            pattern: File pattern to match (default: *.png)

        Returns:
            Batch comparison results
        """
        baseline_path = Path(baseline_dir)
        current_path = Path(current_dir)
        output_path = Path(output_dir)

        output_path.mkdir(parents=True, exist_ok=True)

        results = {
            "total": 0,
            "matched": 0,
            "different": 0,
            "errors": 0,
            "comparisons": []
        }

        # Find all baseline screenshots
        baseline_files = sorted(baseline_path.glob(pattern))

        for baseline_file in baseline_files:
            current_file = current_path / baseline_file.name

            if not current_file.exists():
                results["errors"] += 1
                results["comparisons"].append({
                    "file": baseline_file.name,
                    "status": "error",
                    "message": "Current screenshot not found"
                })
                continue

            # Compare screenshots
            comparison_output = output_path / baseline_file.stem
            result = self.compare_screenshots(
                str(baseline_file),
                str(current_file),
                str(comparison_output)
            )

            results["total"] += 1

            if result["match"]:
                results["matched"] += 1
            else:
                results["different"] += 1

            results["comparisons"].append({
                "file": baseline_file.name,
                **result
            })

        # Generate summary report
        self._generate_report(results, output_path / "report.html")

        return results

    def _generate_report(self, results: Dict[str, Any], output_path: Path):
        """Generate HTML report for batch comparison"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Screenshot Diff Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 40px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}
        .stat {{
            padding: 20px;
            border-radius: 6px;
            text-align: center;
        }}
        .stat.total {{ background: #e3f2fd; }}
        .stat.matched {{ background: #e8f5e9; }}
        .stat.different {{ background: #fff3e0; }}
        .stat.errors {{ background: #ffebee; }}
        .stat-number {{
            font-size: 48px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
        }}
        .comparison {{
            margin: 20px 0;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 6px;
        }}
        .comparison.match {{
            border-left: 4px solid #4caf50;
        }}
        .comparison.different {{
            border-left: 4px solid #ff9800;
        }}
        .comparison.error {{
            border-left: 4px solid #f44336;
        }}
        .comparison-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge.match {{ background: #4caf50; color: white; }}
        .badge.different {{ background: #ff9800; color: white; }}
        .badge.error {{ background: #f44336; color: white; }}
        .images {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }}
        .images img {{
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .metric {{
            display: inline-block;
            margin-right: 20px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Screenshot Diff Report</h1>

        <div class="summary">
            <div class="stat total">
                <div class="stat-label">Total</div>
                <div class="stat-number">{results['total']}</div>
            </div>
            <div class="stat matched">
                <div class="stat-label">Matched</div>
                <div class="stat-number">{results['matched']}</div>
            </div>
            <div class="stat different">
                <div class="stat-label">Different</div>
                <div class="stat-number">{results['different']}</div>
            </div>
            <div class="stat errors">
                <div class="stat-label">Errors</div>
                <div class="stat-number">{results['errors']}</div>
            </div>
        </div>

        <h2>Comparisons</h2>
"""

        for comparison in results["comparisons"]:
            status = "match" if comparison.get("match") else "different"
            if comparison.get("status") == "error":
                status = "error"

            badge_text = "✓ Match" if status == "match" else ("✗ Different" if status == "different" else "⚠ Error")

            html += f"""
        <div class="comparison {status}">
            <div class="comparison-header">
                <h3>{comparison['file']}</h3>
                <span class="badge {status}">{badge_text}</span>
            </div>
"""

            if status != "error" and not comparison.get("match"):
                diff_pct = comparison.get("difference_percentage", 0)
                html += f"""
            <div>
                <span class="metric">Difference: {diff_pct:.2f}%</span>
                <span class="metric">Pixels: {comparison.get('pixel_differences', 0):,}</span>
            </div>
"""

                if "diff_images" in comparison:
                    html += """
            <div class="images">
                <div>
                    <h4>Side-by-Side</h4>
                    <img src="{}" alt="Side by side comparison">
                </div>
                <div>
                    <h4>Diff Highlight</h4>
                    <img src="{}" alt="Diff highlight">
                </div>
            </div>
""".format(
                        os.path.relpath(comparison["diff_images"]["side_by_side"], output_path.parent),
                        os.path.relpath(comparison["diff_images"]["diff"], output_path.parent)
                    )

            html += """
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        output_path.write_text(html)


def main():
    parser = argparse.ArgumentParser(
        description="Screenshot Diffing Tool for iOS Visual Regression Testing"
    )

    parser.add_argument("baseline", help="Baseline screenshot or directory")
    parser.add_argument("current", help="Current screenshot or directory")
    parser.add_argument("-o", "--output", help="Output directory for diff images")
    parser.add_argument(
        "-t", "--threshold",
        type=float,
        default=0.01,
        help="Difference threshold (0.0 to 1.0, default: 0.01)"
    )
    parser.add_argument(
        "--no-ignore-antialiasing",
        action="store_true",
        help="Don't ignore minor antialiasing differences"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode: compare all screenshots in directories"
    )

    args = parser.parse_args()

    # Initialize differ
    differ = ScreenshotDiffer(
        threshold=args.threshold,
        ignore_antialiasing=not args.no_ignore_antialiasing
    )

    # Batch mode
    if args.batch:
        if not os.path.isdir(args.baseline) or not os.path.isdir(args.current):
            print("Error: Batch mode requires both baseline and current to be directories")
            sys.exit(1)

        output_dir = args.output or "./screenshot-diff-results"
        results = differ.batch_compare(args.baseline, args.current, output_dir)

        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print(f"\n📊 Screenshot Diff Results")
            print(f"{'='*50}")
            print(f"Total:     {results['total']}")
            print(f"Matched:   {results['matched']} ✓")
            print(f"Different: {results['different']} ✗")
            print(f"Errors:    {results['errors']} ⚠")
            print(f"\nReport saved to: {output_dir}/report.html")

        sys.exit(0 if results["different"] == 0 and results["errors"] == 0 else 1)

    # Single comparison mode
    if not os.path.isfile(args.baseline) or not os.path.isfile(args.current):
        print("Error: Baseline and current must be image files")
        sys.exit(1)

    result = differ.compare_screenshots(
        args.baseline,
        args.current,
        args.output
    )

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "error":
            print(f"❌ Error: {result['message']}")
            sys.exit(1)

        if result["match"]:
            print(f"✅ Screenshots match (difference: {result['difference_percentage']:.2f}%)")
            sys.exit(0)
        else:
            print(f"❌ Screenshots differ:")
            print(f"   Difference: {result['difference_percentage']:.2f}%")
            print(f"   Different pixels: {result['pixel_differences']:,} / {result['total_pixels']:,}")

            if "diff_images" in result:
                print(f"\nDiff images saved to:")
                print(f"   {result['diff_images']['diff']}")
                print(f"   {result['diff_images']['side_by_side']}")
                print(f"   {result['diff_images']['overlay']}")

            sys.exit(1)


if __name__ == "__main__":
    main()
