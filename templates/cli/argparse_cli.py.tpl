#!/usr/bin/env python3
"""${description} - CLI Tool"""

import argparse
import sys


def cmd_${default_command}(args):
    """Handle the ${default_command} command."""
    ${command_body}


def main():
    parser = argparse.ArgumentParser(
        prog="${prog_name}",
        description="${description}",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ${default_command} command
    sub = subparsers.add_parser("${default_command}", help="${command_help}")
    sub.add_argument("input", help="Input ${input_type}")
    sub.add_argument("-o", "--output", default=None, help="Output path")
    sub.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "${default_command}":
        cmd_${default_command}(args)


if __name__ == "__main__":
    main()
