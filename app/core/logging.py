"""Logging helpers for the API process."""

import logging


def configure_logging() -> None:
    """Configure a concise default logger if the host did not set one."""
    if logging.getLogger().handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
