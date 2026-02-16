#!/usr/bin/env python3
"""${description} - Data Analysis Script"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_data(filepath):
    """Load data from CSV file."""
    df = pd.read_csv(filepath)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    return df


def analyze(df):
    """Run analysis on the dataframe."""
    print("\n--- Basic Statistics ---")
    print(df.describe())

    print("\n--- Data Types ---")
    print(df.dtypes)

    print("\n--- Missing Values ---")
    print(df.isnull().sum())

    return df


def visualize(df, output_dir="."):
    """Create visualizations."""
    numeric_cols = df.select_dtypes(include="number").columns

    if len(numeric_cols) > 0:
        fig, ax = plt.subplots(figsize=(10, 6))
        df[numeric_cols].hist(ax=ax if len(numeric_cols) == 1 else None, figsize=(10, 6))
        plt.tight_layout()
        plt.savefig(f"{output_dir}/analysis_histograms.png", dpi=150)
        print(f"Saved histogram to {output_dir}/analysis_histograms.png")
        plt.close()

    if len(numeric_cols) >= 2:
        fig, ax = plt.subplots(figsize=(10, 6))
        df.plot.scatter(x=numeric_cols[0], y=numeric_cols[1], ax=ax)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/analysis_scatter.png", dpi=150)
        print(f"Saved scatter plot to {output_dir}/analysis_scatter.png")
        plt.close()


def main():
    filepath = "${default_csv}"
    df = load_data(filepath)
    df = analyze(df)
    visualize(df)
    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
