import logging
import os


def configure_logging() -> None:
    """
    One place to set up logging for every entrypoint (API server, scheduler,
    scripts). Timestamps + level + module name make production logs
    searchable in a way bare print() calls never were.

    Level comes from LOG_LEVEL (default INFO) rather than Settings, so this
    can run before — or without — the API keys Settings requires.
    """
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # httpx logs every request at INFO, which drowns out our own logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
