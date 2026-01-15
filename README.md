# s3diff

A Python tool to compare AWS S3 files and directories for content equality. This tool can be used both as a command-line utility and as an importable Python package.

## Features

- Compare individual S3 files or entire directories
- Content-based comparison (ignores metadata differences)
- Uses AWS environment credentials (no hardcoded credentials)
- Detailed difference reporting
- Fast comparison using ETags when possible, with content hashing fallback
- Can be used as CLI tool or imported as Python package

## Installation

### Using UV (recommended)
```bash
# Install from source
git clone https://github.com/somody/s3diff.git
cd s3diff
uv sync

# Or install with development dependencies
uv sync --extra=dev
```

### Using pip
```bash
# Install from source
git clone https://github.com/somody/s3diff.git
cd s3diff
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Usage

### Command Line

```bash
# Compare two files
./s3diff.py s3://bucket1/file.txt s3://bucket2/file.txt

# Compare two directories  
./s3diff.py s3://bucket1/data/ s3://bucket2/backup/

# With verbose output
./s3diff.py -v s3://bucket1/folder s3://bucket2/folder

# After installation as package
s3diff s3://bucket1/path s3://bucket2/path
```

### Python Package

```python
from s3diff import compare_s3_paths, S3Comparer

# Simple comparison
are_identical = compare_s3_paths('s3://bucket1/file.txt', 's3://bucket2/file.txt')

# Advanced usage
comparer = S3Comparer()
result = comparer.compare('s3://bucket1/data/', 's3://bucket2/backup/')
```

## AWS Credentials

The tool uses AWS credentials from environment variables or AWS CLI configuration:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials
export AWS_DEFAULT_REGION=us-east-1          # Optional
```

Or configure using AWS CLI:
```bash
aws configure
```

## Exit Codes

- `0`: Paths are identical
- `1`: Paths are different  
- `2`: Error in arguments or AWS configuration
- `3`: Interrupted by user (Ctrl+C)
- `4`: Unexpected error

## Examples

### File Comparison
```bash
./s3diff.py s3://mybucket/data/file1.json s3://backup-bucket/data/file1.json
```

### Directory Comparison
```bash
./s3diff.py s3://mybucket/logs/2024/ s3://backup-bucket/logs/2024/
```

### Cross-bucket Sync Verification
```bash
./s3diff.py s3://source-bucket/important-data s3://backup-bucket/important-data
```

## How It Works

1. **Path Analysis**: Determines if S3 paths are files or directories
2. **Metadata Comparison**: First compares file sizes and ETags for quick differences
3. **Content Verification**: For small files or when ETags differ, downloads and computes MD5 hashes
4. **Directory Traversal**: For directories, recursively compares all contained objects
5. **Difference Reporting**: Shows files unique to each path and content differences

## Limitations

- Large file comparisons may take time due to content downloading
- Requires appropriate S3 permissions (s3:GetObject, s3:ListBucket, etc.)
- ETag comparison may not work for multipart uploads (falls back to content hashing)
