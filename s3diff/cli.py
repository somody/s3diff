"""Command line interface for S3 diff tool."""

import argparse
import sys
from typing import Optional

from .core import S3Comparer


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        prog='s3diff',
        description='Compare AWS S3 files and directories for content equality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  s3diff s3://bucket1/file.txt s3://bucket2/file.txt
  s3diff s3://bucket1/folder/ s3://bucket2/folder/
  s3diff s3://bucket1/data s3://bucket2/backup/data

The tool uses AWS credentials from environment variables or AWS CLI configuration.
Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and optionally AWS_SESSION_TOKEN.
"""
    )
    
    parser.add_argument(
        'path1',
        help='First S3 path (s3://bucket/key)'
    )
    
    parser.add_argument(
        'path2', 
        help='Second S3 path (s3://bucket/key)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    return parser


def main(args: Optional[list] = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    try:
        comparer = S3Comparer()
        
        if parsed_args.verbose:
            print(f"Initializing S3 client...")
            print(f"Comparing {parsed_args.path1} and {parsed_args.path2}")
        
        are_identical = comparer.compare(parsed_args.path1, parsed_args.path2)
        
        if are_identical:
            print("✓ Paths are identical")
            return 0
        else:
            print("✗ Paths are different")
            return 1
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 4


if __name__ == '__main__':
    sys.exit(main())
