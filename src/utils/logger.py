import logging
import sys

class ExtraFormatter(logging.Formatter):
    """Formatter mặc định + tự động in thêm các field truyền qua extra={...}."""

    # Các attribute "chuẩn" mà LogRecord nào cũng có -> dùng để loại trừ
    _RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self._RESERVED
        }

        if extras:
            extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base} | {extra_str}"

        return base


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Creates and configures a clean, console-only logger.
    No file output, no emojis, standardized text format.
    Automatically appends any `extra={...}` fields to the log line.
    """
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = ExtraFormatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger