#!/usr/bin/env python3
"""
Create sample run manifest for testing
"""

import sys
from pathlib import Path

# Import Huxley modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_manifest", parent_dir / "global" / "config" / "run_manifest.py")
    manifest_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest_module)
    RunManifest = manifest_module.RunManifest
except Exception as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def create_sample_manifest():
    """Create a sample run manifest for testing"""
    
    # Create manifest for example-automation-capsule capsule (if it exists)
    manifest = RunManifest("example-automation-capsule", "sample_20250812_001")
    
    # Set capsule info
    manifest.set_capsule_info(version="1.0.0", lane="standard")
    
    # Add some input parameters
    manifest.add_input_parameters({
        "input_image": "test_jar.jpg",
        "output_format": "png",
        "label_style": "modern"
    })
    
    # Add some DoD checks
    manifest.add_dod_check("Image processing", "passed", "Successfully processed input image")
    manifest.add_dod_check("Label generation", "passed", "Generated label with correct format")
    manifest.add_dod_check("Output validation", "passed", "Output file meets requirements")
    
    # Add test results
    manifest.set_test_results(total=5, passed=5, failed=0, skipped=0, coverage_percent=85.0)
    
    # Add some artifacts
    manifest.add_artifact("output/labeled_jar.png", "data", "Final labeled jar image")
    manifest.add_artifact("logs/processing.log", "log", "Processing execution log")
    
    # Add structured logs
    manifest.add_structured_log("INFO", "Starting image processing", "processor")
    manifest.add_structured_log("INFO", "Image loaded successfully", "loader")
    manifest.add_structured_log("INFO", "Label applied", "labeler")
    manifest.add_structured_log("INFO", "Processing completed", "processor")
    
    # Finish execution
    manifest.finish_execution(exit_code=0, status="completed")
    
    # Save manifest
    manifest_path = manifest.save_manifest()
    print(f"Created sample manifest: {manifest_path}")
    
    return manifest_path

if __name__ == "__main__":
    create_sample_manifest()