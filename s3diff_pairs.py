#!/usr/bin/env python3
"""
Script to find and compare S3 folder pairs that differ only by suffixes.
Compares folders like 'base_folder/' with 'base_folder_Drug_Seq/' etc.
"""

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Set


def run_aws_s3_ls(s3_path: str) -> List[str]:
    """Run 'aws s3 ls' and return list of folder names."""
    try:
        cmd = ['aws', 's3', 'ls', s3_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        folders = []
        for line in result.stdout.strip().split('\n'):
            if line.strip() and 'PRE ' in line:
                # Extract folder name from "PRE folder_name/"
                folder = line.split('PRE ')[-1].strip()
                if folder.endswith('/'):
                    folder = folder[:-1]  # Remove trailing slash
                folders.append(folder)
        
        return folders
    
    except subprocess.CalledProcessError as e:
        print(f"Error running AWS CLI: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: AWS CLI not found. Please install AWS CLI.")
        sys.exit(1)


def extract_base_name(folder_name: str) -> str:
    """Extract base name by removing known suffixes."""
    # Define suffix patterns to remove (order matters - most specific first)
    suffix_patterns = [
        r'_\d+_Drug_[Ss]eq_.*$',    # _240_Drug_Seq with additional suffixes
        r'_\d+_Drug_[Ss]eq$',       # _240_Drug_Seq or _240_Drug_seq
        r'_Drug_[Ss]eq_.*$',        # _Drug_Seq with additional suffixes
        r'_Drug_[Ss]eq$',           # _Drug_Seq or _Drug_seq
    ]
    
    base_name = folder_name
    for pattern in suffix_patterns:
        base_name = re.sub(pattern, '', base_name)
        if base_name != folder_name:  # If a pattern matched, stop processing
            break
    
    return base_name


def group_folders_by_base(folders: List[str]) -> Dict[str, List[str]]:
    """Group folders by their base names."""
    groups = defaultdict(list)
    
    for folder in folders:
        base_name = extract_base_name(folder)
        groups[base_name].append(folder)
    
    return dict(groups)


def find_folder_pairs(folder_groups: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Find pairs of folders (base + suffixed versions)."""
    pairs = []
    
    for base_name, group_folders in folder_groups.items():
        if len(group_folders) == 2:
            # Sort to ensure consistent ordering (base first, then suffixed)
            sorted_folders = sorted(group_folders, key=len)
            pairs.append((sorted_folders[0], sorted_folders[1]))
        elif len(group_folders) > 2:
            print(f"Warning: Found {len(group_folders)} folders for base '{base_name}': {group_folders}")
    
    return pairs


def run_s3diff(s3_path1: str, s3_path2: str, dry_run: bool = False) -> bool:
    """Run s3diff comparison between two S3 paths."""
    if dry_run:
        print(f"[DRY RUN] Would compare: {s3_path1} <-> {s3_path2}")
        return True
    
    try:
        # Use the s3diff script from the current directory
        script_path = Path(__file__).parent / "s3diff.py"
        cmd = [sys.executable, str(script_path), s3_path1, s3_path2]
        
        print(f"Comparing: {s3_path1} <-> {s3_path2}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Error: {result.stderr}", file=sys.stderr)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"Error running s3diff: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Find and compare S3 folder pairs that differ only by suffixes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be compared
  python s3diff_pairs.py s3://bucket/path/ --dry-run
  
  # Actually run comparisons  
  python s3diff_pairs.py s3://bucket/path/
  
  # Only show pairs, don't run comparisons
  python s3diff_pairs.py s3://bucket/path/ --list-only
"""
    )
    
    parser.add_argument(
        's3_path',
        help='S3 path to scan for folder pairs (e.g., s3://bucket/path/)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be compared without actually running s3diff'
    )
    
    parser.add_argument(
        '--list-only',
        action='store_true', 
        help='Only list the pairs found, don\'t run any comparisons'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Ensure S3 path ends with /
    s3_path = args.s3_path
    if not s3_path.endswith('/'):
        s3_path += '/'
    
    if args.verbose:
        print(f"Scanning S3 path: {s3_path}")
    
    # Get list of folders
    print("Fetching folder list from S3...")
    folders = run_aws_s3_ls(s3_path)
    
    if args.verbose:
        print(f"Found {len(folders)} folders:")
        for folder in folders:
            print(f"  {folder}")
        print()
    
    # Group folders by base name
    folder_groups = group_folders_by_base(folders)
    
    # Find pairs
    pairs = find_folder_pairs(folder_groups)
    
    if not pairs:
        print("No folder pairs found.")
        return 0
    
    print(f"Found {len(pairs)} folder pairs:")
    for base_folder, suffixed_folder in pairs:
        print(f"  {base_folder} <-> {suffixed_folder}")
    
    if args.list_only:
        return 0
    
    print()
    
    # Run comparisons
    success_count = 0
    total_count = len(pairs)
    
    for i, (base_folder, suffixed_folder) in enumerate(pairs, 1):
        print(f"=== Comparison {i}/{total_count} ===")
        
        s3_path1 = f"{s3_path}{base_folder}/"
        s3_path2 = f"{s3_path}{suffixed_folder}/"
        
        success = run_s3diff(s3_path1, s3_path2, args.dry_run)
        if success:
            success_count += 1
        
        print()
    
    # Summary
    if not args.dry_run:
        print(f"=== Summary ===")
        print(f"Completed {total_count} comparisons")
        print(f"Identical pairs: {success_count}/{total_count}")
        print(f"Different pairs: {total_count - success_count}/{total_count}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())