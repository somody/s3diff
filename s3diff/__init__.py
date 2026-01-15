"""S3 Diff - Compare AWS S3 files and directories."""

from .core import S3Comparer, compare_s3_paths
from .cli import main

__version__ = "1.0.0"
__author__ = "S3Diff"

__all__ = ["S3Comparer", "compare_s3_paths", "main"]
