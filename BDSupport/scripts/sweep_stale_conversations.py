"""scripts/sweep_stale_conversations.py

Wire this up to a real scheduler (cron, Windows Task Scheduler, systemd
timer) every 5-10 minutes so a reported issue that goes quiet still becomes
a ticket in a timely, guaranteed way - not just whenever some other user
happens to message the bot (core/intake/sweep.sweep_stale is also called
opportunistically from rag/flow.py, but that's a best-effort supplement to
this, not a replacement for it).

Usage:
    python scripts/sweep_stale_conversations.py [minutes]

`minutes` overrides STALE_TICKET_MINUTES for this run (e.g. for testing
with a short window). Exits 0 always; failures are logged, not raised, so a
cron entry doesn't need special error handling.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sweep_stale_conversations")


def main() -> int:
    from core.intake.sweep import sweep_stale

    max_age_minutes = None
    if len(sys.argv) > 1:
        try:
            max_age_minutes = float(sys.argv[1])
        except ValueError:
            logger.error("Invalid minutes argument: %s", sys.argv[1])
            return 0

    created = sweep_stale(max_age_minutes=max_age_minutes, force=True)
    logger.info("Sweep complete - %d ticket(s) auto-created", created)
    return 0


if __name__ == "__main__":
    sys.exit(main())
