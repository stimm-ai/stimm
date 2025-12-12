"""
Centralized logging configuration for the Stimm platform.
This ensures consistent logging behavior across CLI, Agent Worker, and Backend Server.
"""

import logging
import os
import sys


def configure_logging(verbose: bool = False):
    """
    Configure logging for the application.

    Args:
        verbose: If True, enable DEBUG level logs for application modules.
                 If False, use INFO level and suppress noisy libraries.
    """
    # Determine requested log level from arg or env
    env_level = os.getenv("LOG_LEVEL", "").upper()
    if env_level == "DEBUG":
        verbose = True

    # 1. Root Logger Configuration
    # We set root to WARNING by default to silence noisy libraries (aiohttp, livekit, etc.)
    # unless we are in verbose mode, where we might want to see them (or keep them at INFO).
    # If verbose is True, we set root to INFO to see library events, but NOT DEBUG (too noisy).
    root_level = logging.INFO if verbose else logging.WARNING

    logging.basicConfig(
        level=root_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # CRITICAL: Override any existing config from imported libraries
    )

    # 2. Application Loggers Configuration
    # These are the loggers for our code. We want them to be INFO (clean) or DEBUG (detailed).
    app_level = logging.DEBUG if verbose else logging.INFO

    app_loggers = ["src", "services", "cli", "agent-worker", "__main__"]

    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(app_level)
        # Ensure they propagate to root handler
        logger.propagate = True

    # 3. Specific Overrides
    # Some libraries are useful to see at INFO even in non-verbose mode if needed,
    # or suppress even in verbose mode if too spammy.

    # Silence asyncio selector logs
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # If verbose, we might want LiveKit SDK logs to remain at INFO, not DEBUG
    # (LiveKit DEBUG is extremely verbose)
    if verbose:
        logging.getLogger("livekit").setLevel(logging.INFO)
        logging.getLogger("aiohttp").setLevel(logging.INFO)

    # Log the configuration result
    logging.getLogger("src.utils.logging_config").info(f"✅ Logging configured. Level: {logging.getLevelName(app_level)} (Verbose: {verbose})")
