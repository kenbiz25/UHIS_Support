"""scripts/sweep_csat.py

Wire this up to a real scheduler (cron, Windows Task Scheduler, systemd
timer) every 10-15 minutes so a resolved ticket gets its "how did we do?"
WhatsApp survey in a timely, guaranteed way - core/tickets/csat_sweep.py is
also called opportunistically from rag/flow.py on inbound traffic, but
that's a best-effort supplement to this, not a replacement for it (nobody
messaging the bot for a while would otherwise delay every pending survey).

Usage:
    python scripts/sweep_csat.py [minutes]

`minutes` overrides CSAT_DELAY_MINUTES for this run (e.g. for testing with
a short window). Exits 0 always; failures are logged, not raised, so a
cron entry doesn't need special error handling.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sweep_csat")


def main() -> int:
    from core.tickets.csat_sweep import sweep_csat

    max_age_minutes = None
    if len(sys.argv) > 1:
        try:
            max_age_minutes = float(sys.argv[1])
        except ValueError:
            logger.error("Invalid minutes argument: %s", sys.argv[1])
            return 0

    sent = sweep_csat(max_age_minutes=max_age_minutes, force=True)
    logger.info("Sweep complete - %d CSAT prompt(s) sent", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
