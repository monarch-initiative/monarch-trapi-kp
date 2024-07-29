"""
Testing LoggingUtil (and LoggerWrapper inside)
"""
import logging
from mmcq.services.util.logutil import LoggerWrapper, LoggingUtil

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def test_logger_wrapper():
    lw = LoggerWrapper(logger)
    lw.debug("Testing Logger Wrapper")


def test_logger_util():
    lu = LoggingUtil.init_logging(__name__)
    lu.debug("Testing Logging Util class")
