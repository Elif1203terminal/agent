#!/usr/bin/env python3
"""${description} - Data Visualization Script"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def create_bar_chart(df, x_col, y_col, title, output_path):
    """Create a bar chart."""
    fig, ax = plt.subplots(figsize=(10, 6))
    df.plot.bar(x=x_col, y=y_col, ax=ax)
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")
    plt.close()


def create_line_chart(df, x_col, y_col, title, output_path):
    """Create a line chart."""
    fig, ax = plt.subplots(figsize=(10, 6))
    df.plot.line(x=x_col, y=y_col, ax=ax)
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")
    plt.close()


def create_pie_chart(df, label_col, value_col, title, output_path):
    """Create a pie chart."""
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(df[value_col], labels=df[label_col], autopct="%1.1f%%")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")
    plt.close()


def main():
    filepath = "${default_csv}"
    df = pd.read_csv(filepath)
    print(f"Loaded {len(df)} rows")
    print(f"Columns: {list(df.columns)}")

    # Generate visualizations for numeric columns
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        create_bar_chart(df.head(20), df.columns[0], numeric_cols[0],
                        "${app_name} - Bar Chart", "bar_chart.png")

    print("Visualization complete.")


if __name__ == "__main__":
    main()
