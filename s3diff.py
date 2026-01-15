#!/usr/bin/env python3
"""Executable script for s3diff tool."""

import sys
import os

# Add the current directory to Python path so we can import s3diff
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s3diff.cli import main

if __name__ == '__main__':
    sys.exit(main())
