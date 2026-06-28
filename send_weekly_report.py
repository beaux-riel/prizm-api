#!/usr/bin/env python3
"""Send the configured PRIZM weekly report email.

Intended for a Railway cron worker or manual Railway shell invocation:

    python send_weekly_report.py
"""

from app import build_weekly_report, send_weekly_report_email


def main() -> None:
    report = build_weekly_report()
    recipients = send_weekly_report_email(report)
    print(f"Sent PRIZM weekly report to {', '.join(recipients)}")


if __name__ == "__main__":
    main()
