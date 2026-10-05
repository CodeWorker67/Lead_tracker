"""Аудит входа/выхода админки — stdlib logging (виден в docker compose logs admin)."""

import logging
import sys

_LOGGER_NAME = "lead_tracker.admin.auth"


def _audit_logger() -> logging.Logger:
    log = logging.getLogger(_LOGGER_NAME)
    if log.level == logging.NOTSET:
        log.setLevel(logging.INFO)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        log.addHandler(handler)
        log.propagate = True
    return log


def _emit(log_fn, message: str, *args: object) -> None:
    log_fn(message, *args)
    sys.stdout.flush()


def audit_info(message: str, *args: object) -> None:
    _emit(_audit_logger().info, message, *args)


def audit_warning(message: str, *args: object) -> None:
    _emit(_audit_logger().warning, message, *args)
