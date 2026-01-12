import logging
import logging.config
import sys
from app.config import get_settings

def setup_logging():
    """
    Configure global log format
    Standardize log output format for all loggers including uvicorn and third-party libraries.
    """
    settings = get_settings()
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "root": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": True,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "app": {  # Configure our application logger specifically if needed
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)