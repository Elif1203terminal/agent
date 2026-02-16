#!/usr/bin/env python3
"""${description} - Scheduled task runner."""

import time
import datetime


def task():
    """The task to run on schedule."""
    ${task_body}


def main():
    interval_seconds = ${interval}
    print(f"Starting scheduler - running every {interval_seconds}s")
    print("Press Ctrl+C to stop")

    try:
        while True:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now}] Running task...")
            task()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()
