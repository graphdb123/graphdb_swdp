
from colorama import Fore, Style
import time

import logging

logger = logging.getLogger(__name__)

LEVEL_COLORS = {
    "DEBUG": Fore.BLUE,
    "INFO": Fore.GREEN,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED,
}


def setup_logger(level, file_path=False):
    if not file_path:
        handler = logging.StreamHandler()
        handler.setFormatter(OdooMigrateFormatter())
    else:
        handler = logging.FileHandler(file_path)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s"
            )
        )
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, str(level)))


class OdooMigrateFormatter(logging.Formatter):
    def format(self, record):
        """Overwrite format() function to use custom formatter"""
        record.message = record.getMessage()
        record.asctime = time.strftime("%H:%M:%S", self.converter(record.created))

        prefix = self.default_prefix_template(record) % record.__dict__
        return (prefix + " " + record.message).replace("\n", "\n" + "".ljust(23, " "))

    def default_prefix_template(self, record):
        """Return the prefix for the log message. Template for Formatter.

        :param: record: :py:class:`logging.LogRecord` object. this is passed in
        from inside the :py:meth:`logging.Formatter.format` record.

        """
        reset = [Style.RESET_ALL]
        levelname = [
            LEVEL_COLORS.get(record.levelname),
            Style.BRIGHT,
            "%(levelname)-10s",
            Style.RESET_ALL,
            " ",
        ]
        asctime = [
            "",
            Fore.BLACK,
            Style.DIM,
            Style.BRIGHT,
            "%(asctime)-10s",
            Fore.RESET,
            Style.RESET_ALL,
            " ",
        ]

        return "".join(reset + asctime + levelname + reset)
