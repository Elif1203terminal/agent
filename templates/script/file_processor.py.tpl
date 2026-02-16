#!/usr/bin/env python3
"""${description} - File processing script."""

import os
import sys
import shutil
from pathlib import Path


def process_file(filepath):
    """Process a single file."""
    ${process_logic}


def process_directory(directory):
    """Process all files in the given directory."""
    directory = Path(directory)
    if not directory.is_dir():
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)

    processed = 0
    for filepath in directory.iterdir():
        if filepath.is_file():
            process_file(filepath)
            processed += 1

    print(f"Processed {processed} files in {directory}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python ${script_name} <directory>")
        sys.exit(1)

    target = sys.argv[1]
    process_directory(target)


if __name__ == "__main__":
    main()
