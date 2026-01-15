"""Core S3 comparison functionality."""

import os
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class S3Path:
    """Represents an S3 path with bucket and key components."""
    
    def __init__(self, s3_url: str):
        self.url = s3_url
        parsed = urlparse(s3_url)
        if parsed.scheme != 's3':
            raise ValueError(f"Invalid S3 URL: {s3_url}. Must start with 's3://'")
        
        self.bucket = parsed.netloc
        self.key = parsed.path.lstrip('/')
        
        if not self.bucket:
            raise ValueError(f"Invalid S3 URL: {s3_url}. Bucket name is required")
    
    def __str__(self):
        return self.url
    
    def __repr__(self):
        return f"S3Path('{self.url}')"


class S3Object:
    """Represents an S3 object with metadata."""
    
    def __init__(self, bucket: str, key: str, size: int, etag: str):
        self.bucket = bucket
        self.key = key
        self.size = size
        self.etag = etag.strip('"')  # Remove quotes from ETag
    
    def __eq__(self, other):
        if not isinstance(other, S3Object):
            return False
        return self.key == other.key and self.size == other.size
    
    def __hash__(self):
        return hash((self.key, self.size))
    
    def __str__(self):
        return f"s3://{self.bucket}/{self.key}"


class S3Comparer:
    """Compare S3 files and directories."""
    
    def __init__(self):
        try:
            self.s3_client = boto3.client('s3')
            # Test credentials by listing buckets (this will fail if no credentials)
            self.s3_client.list_buckets()
        except NoCredentialsError:
            raise ValueError(
                "AWS credentials not found. Please set AWS_ACCESS_KEY_ID, "
                "AWS_SECRET_ACCESS_KEY, and optionally AWS_SESSION_TOKEN "
                "environment variables, or configure AWS CLI."
            )
        except ClientError as e:
            raise ValueError(f"Failed to initialize S3 client: {e}")
    
    def _object_exists(self, bucket: str, key: str) -> bool:
        """Check if an S3 object exists."""
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def _is_directory(self, bucket: str, key: str) -> bool:
        """Check if the S3 path represents a directory (prefix)."""
        if not key or key.endswith('/'):
            return True
        
        # Check if it's a file first
        if self._object_exists(bucket, key):
            return False
        
        # Check if there are objects with this prefix
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=key + '/' if not key.endswith('/') else key,
                MaxKeys=1
            )
            return response.get('KeyCount', 0) > 0
        except ClientError:
            return False
    
    def _list_objects(self, bucket: str, prefix: str) -> List[S3Object]:
        """List all objects under a given prefix."""
        objects = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    objects.append(S3Object(
                        bucket=bucket,
                        key=obj['Key'],
                        size=obj['Size'],
                        etag=obj['ETag']
                    ))
        except ClientError as e:
            raise ValueError(f"Failed to list objects in s3://{bucket}/{prefix}: {e}")
        
        return objects
    
    def _get_single_object(self, bucket: str, key: str) -> S3Object:
        """Get metadata for a single S3 object."""
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            return S3Object(
                bucket=bucket,
                key=key,
                size=response['ContentLength'],
                etag=response['ETag']
            )
        except ClientError as e:
            raise ValueError(f"Failed to get object s3://{bucket}/{key}: {e}")
    

    
    def _normalize_relative_path(self, base_prefix: str, full_key: str) -> str:
        """Get the relative path from a base prefix."""
        if base_prefix and not base_prefix.endswith('/'):
            base_prefix += '/'
        return full_key[len(base_prefix):] if full_key.startswith(base_prefix) else full_key
    
    def compare_files(self, path1: S3Path, path2: S3Path) -> bool:
        """Compare two S3 files for content equality using size and ETag."""
        obj1 = self._get_single_object(path1.bucket, path1.key)
        obj2 = self._get_single_object(path2.bucket, path2.key)
        
        # Check sizes
        if obj1.size != obj2.size:
            print(f"Files differ in size: {obj1.size} vs {obj2.size} bytes")
            return False
        
        # Check ETags (AWS S3's content hash)
        if obj1.etag != obj2.etag:
            print(f"Files differ in content (ETag): {obj1.etag} vs {obj2.etag}")
            return False
        
        return True
    
    def compare_directories(self, path1: S3Path, path2: S3Path) -> bool:
        """Compare two S3 directories for content equality."""
        # Ensure prefixes end with / for proper directory listing
        prefix1 = path1.key
        prefix2 = path2.key
        if prefix1 and not prefix1.endswith('/'):
            prefix1 += '/'
        if prefix2 and not prefix2.endswith('/'):
            prefix2 += '/'
        
        objects1 = self._list_objects(path1.bucket, prefix1)
        objects2 = self._list_objects(path2.bucket, prefix2)
        
        # Create dictionaries mapping relative paths to objects
        dict1 = {
            self._normalize_relative_path(prefix1, obj.key): obj 
            for obj in objects1
        }
        dict2 = {
            self._normalize_relative_path(prefix2, obj.key): obj 
            for obj in objects2
        }
        
        # Check for files only in path1
        only_in_1 = set(dict1.keys()) - set(dict2.keys())
        if only_in_1:
            print(f"Files only in {path1}:")
            for rel_path in sorted(only_in_1):
                print(f"  {rel_path}")
        
        # Check for files only in path2
        only_in_2 = set(dict2.keys()) - set(dict1.keys())
        if only_in_2:
            print(f"Files only in {path2}:")
            for rel_path in sorted(only_in_2):
                print(f"  {rel_path}")
        
        # Check common files for differences
        common_files = set(dict1.keys()) & set(dict2.keys())
        different_files = []
        
        for rel_path in common_files:
            obj1 = dict1[rel_path]
            obj2 = dict2[rel_path]
            
            # Size check
            if obj1.size != obj2.size:
                different_files.append((rel_path, f"Size: {obj1.size} vs {obj2.size}"))
                continue
            
            # ETag comparison (AWS S3's content hash)
            if obj1.etag != obj2.etag:
                different_files.append((rel_path, f"Content differs (ETag: {obj1.etag} vs {obj2.etag})"))
        
        if different_files:
            print(f"Files with different content:")
            for rel_path, reason in different_files:
                print(f"  {rel_path}: {reason}")
        
        # Return True only if no differences found
        return len(only_in_1) == 0 and len(only_in_2) == 0 and len(different_files) == 0
    
    def compare(self, path1_str: str, path2_str: str) -> bool:
        """Compare two S3 paths (files or directories)."""
        path1 = S3Path(path1_str)
        path2 = S3Path(path2_str)
        
        print(f"Comparing {path1} and {path2}...")
        
        # Determine if paths are files or directories
        is_dir1 = self._is_directory(path1.bucket, path1.key)
        is_dir2 = self._is_directory(path2.bucket, path2.key)
        
        if is_dir1 != is_dir2:
            print(f"Cannot compare: {path1} is {'directory' if is_dir1 else 'file'}, "
                  f"{path2} is {'directory' if is_dir2 else 'file'}")
            return False
        
        if is_dir1 and is_dir2:
            return self.compare_directories(path1, path2)
        else:
            return self.compare_files(path1, path2)


def compare_s3_paths(path1: str, path2: str) -> bool:
    """Convenience function to compare two S3 paths."""
    comparer = S3Comparer()
    return comparer.compare(path1, path2)
