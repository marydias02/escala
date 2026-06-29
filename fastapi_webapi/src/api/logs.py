import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename in [logging.__file__, __file__]:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logger(debug=False) -> None:
    logger.remove()
    logger.add(sys.stderr, level="TRACE" if debug else "DEBUG", diagnose=debug)

    try:
        from uvicorn import config

        uvi_log_cfg = config.LOGGING_CONFIG
        uvi_log_cfg["formatters"]["access"]["fmt"] = "%(asctime)s | %(levelname)-8s | uvicorn.access  - %(message)s"
        uvi_log_cfg["handlers"]["access"]["stream"] = "ext://sys.stderr"
        uvi_log_cfg["formatters"]["default"]["fmt"] = "%(asctime)s | %(levelname)-8s | uvicorn.default - %(message)s"
    except ImportError:
        pass

    logging.root.handlers.clear()
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "asyncio", "starlette"):
        std_logger = logging.getLogger(name)
        std_logger.handlers.clear()
        std_logger.propagate = True
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)
