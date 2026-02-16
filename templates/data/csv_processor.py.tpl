#!/usr/bin/env python3
"""${description} - CSV Processing Script"""

import csv
import os
import sys


def read_csv(filepath):
    """Read a CSV file and return rows as list of dicts."""
    with open(filepath, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def process_rows(rows):
    """Process CSV rows."""
    print(f"Processing {len(rows)} rows...")
    ${process_logic}
    return rows


def write_csv(rows, filepath):
    """Write processed rows to a new CSV file."""
    if not rows:
        print("No data to write.")
        return
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Written {len(rows)} rows to {filepath}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python ${script_name} <input.csv> [output.csv]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output.csv"

    rows = read_csv(input_file)
    rows = process_rows(rows)
    write_csv(rows, output_file)


if __name__ == "__main__":
    main()
