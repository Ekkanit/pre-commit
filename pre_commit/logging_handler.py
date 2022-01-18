from __future__ import annotations

import contextlib
import logging
from typing import Generator

from pre_commit import color
from pre_commit import output

logger = logging.getLogger('pre_commit')

LOG_LEVEL_COLORS = {
    'DEBUG': '',
    'INFO': '',
    'WARNING': color.YELLOW,
    'ERROR': color.RED,
}


class LoggingHandler(logging.Handler):
    def __init__(self, use_color: bool) -> None:
        super().__init__()
        self.use_color = use_color

    def emit(self, record: logging.LogRecord) -> None:
        level_msg = color.format_color(
            f'[{record.levelname}]',
            LOG_LEVEL_COLORS[record.levelname],
            self.use_color,
        )
        output.write_line(f'{level_msg} {record.getMessage()}')


@contextlib.contextmanager
def logging_handler(use_color: bool) -> Generator[None, None, None]:
    handler = LoggingHandler(use_color)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        logger.removeHandler(handler)
