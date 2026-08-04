"""Bioimage analysis domain configuration for the pipeline."""

from pathlib import Path
from bioio import BioImage
from config import PipelineConfig


AVAILABLE_LIBRARIES = """
Available libraries for imports:
- Standard library: os, sys, re, csv, json, pathlib, tempfile, subprocess, datetime
- NumPy: for numerical computing
- SciPy: for scientific computing
- scikit-image: for image processing
- scikit-learn: for machine learning
- pandas: for data manipulation
- bioio: for reading biological image formats (TIFF, OME, etc.)
- bioio-tifffile: TIFF file support for bioio
"""

DOMAIN_NOTES = """Use bioio.BioImage for image loading where necessary (from bioio import BioImage)"""


def extract_input_metadata(directory: str) -> str:
    """Extract metadata from multi-channel TIFF images using bioio."""
    metadata_list = []

    for file_path in sorted(Path(directory).glob('*.tif*')):
        try:
            img = BioImage(str(file_path))
            metadata = {
                "filename": file_path.name,
                "shape": dict(zip(img.dims.order, img.shape)),
                "dtype": str(img.dtype),
                "ndim": len(img.shape),
            }

            if hasattr(img, 'channel_names') and img.channel_names:
                metadata["channel_names"] = list(img.channel_names)

            metadata_list.append(metadata)
        except Exception as e:
            metadata_list.append({
                "filename": file_path.name,
                "error": str(e)
            })

    return str(metadata_list)


CONFIG = PipelineConfig(
    orchestrator_model="claude-opus-4-8",
    worker_model="claude-haiku-4-5",
    compiler_model="claude-sonnet-5",
    requirements_evaluator_model="claude-sonnet-5",
    angle_model="claude-haiku-4-5",
    # D5 judging: frontier tier, matching orchestrator_model - once req_score is gone these two
    # judges (insight/soundness) are the entire quality bar (DIVERGER_PLAN.md §5).
    judge_model="claude-opus-4-8",
    docker_image="bia-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
)
