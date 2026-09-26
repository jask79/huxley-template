"""
Huxley Media Workflow Engine

A media-type agnostic workflow orchestration framework. Defines configurable
production pipelines for any media format — image, video, vector, transcode,
timeline composition, 3D rendering, video editing, and future media types.
Each media type plugs into the same infrastructure: YAML workflow configs,
4-layer config inheritance, evaluation loops, provenance tracking, caching,
batch production, and pipeline chaining.

Supported media types:
  - image:      AI image generation (DALL-E, Gemini, Flux)
  - video:      AI video generation (Sora 2, Veo 3)
  - vector:     Programmatic SVG generation (local, no API)
  - 3d-render:  Blender headless rendering (planned — 3D Developer agent)
  - video-edit: DaVinci Resolve automation (planned — Studio Engineer agent)

Tier 1-3 tools (v0.6.0):
  - PyAV:   Batch transcoding, frame extraction, media inspection
  - OTIO:   Timeline composition, EDL/FCPXML/OTIO export
  - MLT:    Headless timeline rendering via melt CLI

Usage:
    from engine import ConfigLoader, ConfigResolver, MediaGenerator, Evaluator, ProvenanceLogger
    from engine import ReferenceManager, OpenRouterClient, ImageToVideoPipeline
    from engine import WorkflowOrchestrator, PromptCache, ABEvalHarness
    from engine import PyAVProcessor, OTIOTimeline, ClipSpec, MarkerSpec, MLTRenderer
"""

from engine.loader import ConfigLoader
from engine.resolver import ConfigResolver
from engine.generator import MediaGenerator
from engine.evaluator import Evaluator
from engine.provenance import ProvenanceLogger
from engine.references import ReferenceManager
from engine.api_client import OpenRouterClient
from engine.pipeline import ImageToVideoPipeline
from engine.orchestrator import WorkflowOrchestrator
from engine.cache import PromptCache
from engine.ab_eval import ABEvalHarness
from engine.pyav_processor import PyAVProcessor
from engine.otio_timeline import OTIOTimeline, ClipSpec, MarkerSpec
from engine.mlt_renderer import MLTRenderer

__all__ = [
    "ConfigLoader",
    "ConfigResolver",
    "MediaGenerator",
    "Evaluator",
    "ProvenanceLogger",
    "ReferenceManager",
    "OpenRouterClient",
    "ImageToVideoPipeline",
    "WorkflowOrchestrator",
    "PromptCache",
    "ABEvalHarness",
    "PyAVProcessor",
    "OTIOTimeline",
    "ClipSpec",
    "MarkerSpec",
    "MLTRenderer",
]

__version__ = "0.6.0"
