#!/usr/bin/env python3
"""${description} - CLI Tool (click-based)"""

import click


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """${description}"""
    pass


@cli.command()
@click.argument("input_path")
@click.option("-o", "--output", default=None, help="Output path")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
def ${default_command}(input_path, output, verbose):
    """${command_help}"""
    if verbose:
        click.echo(f"Processing: {input_path}")
    ${command_body}
    click.echo("Done.")


if __name__ == "__main__":
    cli()
