from typing import Any, List, Dict
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from uuid import UUID

from reasoner_pydantic.shared import LogEntry, LogLevelEnum


class LoggerWrapper(logging.LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra)
        self.query_log: Dict[UUID, List[Dict[str, Any]]] = {}

    def process(self, msg, kwargs):
        """
        Process the logging message and keyword arguments passed in to
        a logging call to insert contextual information. You can either
        manipulate the message itself, the keyword args or both. Return
        the message and kwargs modified (or not) to suit your needs.

        Normally, you'll only need to override this one method in a
        LoggerAdapter subclass for your specific needs.
        """
        # use this stub to capture the messages
        # here, for MMCQ TRAPI LogEntity reporting
        if "query_id" in kwargs:
            query_id = kwargs.pop("query_id")
            if query_id:
                if query_id not in self.query_log:
                    self.query_log[query_id] = []
                log_entry: LogEntry = LogEntry(
                    timestamp=datetime.now(),
                    level=kwargs.pop("level") if "level" in kwargs else None,
                    # TODO: unsure if this needs to be set?
                    # "code": Optional[str] = Field(None, nullable=True)
                    message=msg
                )
                self.query_log[query_id].append(log_entry.to_dict())
        # sanity check - in case the 'level' key is still
        # present, because it was not processed above
        if "level" in kwargs:
            kwargs.pop("level")
        return msg, kwargs

    def get_logs(self, query_id: UUID) -> List[Dict[str, str]]:
        if query_id in self.query_log:
            return [
                {field: str(value) for field, value in entry.items()}
                for entry in self.query_log[query_id]
            ]
        else:
            return []

    def debug(self, msg, /, *args, query_id: UUID = None, **kwargs):
        """
        Delegate a debug call to the underlying logger
        after capturing the message for later export
        """
        kwargs["query_id"] = query_id
        kwargs["level"] = LogLevelEnum.debug
        msg, kwargs = self.process(msg, kwargs)
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, /, *args, query_id: UUID = None, **kwargs):
        """
        Delegate an info call to the underlying logger
        after capturing the message for later export
        """
        kwargs["query_id"] = query_id
        kwargs["level"] = LogLevelEnum.info
        msg, kwargs = self.process(msg, kwargs)
        self.logger.debug(msg, *args, **kwargs)

    def warning(self, msg, /, *args, query_id: UUID = None, **kwargs):
        """
        Delegate a warning call to the underlying logger
        after capturing the message for later export
        """
        kwargs["query_id"] = query_id
        kwargs["level"] = LogLevelEnum.warning
        msg, kwargs = self.process(msg, kwargs)
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, /, *args, query_id: UUID = None, **kwargs):
        """
        Delegate an error call to the underlying logger
        after capturing the message for later export
        """
        kwargs["query_id"] = query_id
        kwargs["level"] = LogLevelEnum.error
        msg, kwargs = self.process(msg, kwargs)
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, /, *args, query_id: UUID = None, **kwargs):
        """
        Delegate a critical call to the underlying logger
        after capturing the message for later export
        """
        kwargs["query_id"] = query_id
        # should be "critical" but LogLevelEnum doesn't have the code
        kwargs["level"] = LogLevelEnum.error
        msg, kwargs = self.process(msg, kwargs)
        self.logger.critical(msg, *args, **kwargs)


class LoggingUtil(object):
    """ Logging utility controlling format and setting initial logging level """

    @staticmethod
    def init_logging(name, level=logging.INFO, format_sel='medium', log_file_level=None):

        log_file_path = os.path.join(os.path.dirname(__file__), '../../logs/mmcq.log')

        # get a logger
        logger = logging.getLogger(__name__)

        # returns a new logger if it's not the root
        if not logger.parent.name == 'root':
            return LoggerWrapper(logger)

        # define the output types
        format_types = {
            "short": '[%(name)s.%(funcName)s] : %(message)s',
            "medium": '[%(name)s.%(funcName)s] - %(asctime)-15s: %(message)s',
            "long": '[%(name)s.%(funcName)s] - %(asctime)-15s %(filename)s %(levelname)s: %(message)s'
        }[format_sel]

        # create a stream handler (default to console)
        stream_handler = logging.StreamHandler()

        # create a formatter
        formatter = logging.Formatter(format_types)

        # set the formatter on the console stream
        stream_handler.setFormatter(formatter)

        # get the name of this logger
        logger = logging.getLogger(name)

        # set the logging level
        logger.setLevel(level)

        # if there was a file path passed in use it
        if log_file_path is not None:
            # create a rotating file handler, 100mb max per file with a max number of 10 files
            file_handler = RotatingFileHandler(filename=log_file_path, maxBytes=1000000, backupCount=10)

            # set the formatter
            file_handler.setFormatter(formatter)

            # if a log level for the file was passed in use it
            if log_file_level is not None:
                level = log_file_level

            # set the log level
            file_handler.setLevel(level)

            # add the handler to the logger
            logger.addHandler(file_handler)

        # add the console handler to the logger
        logger.addHandler(stream_handler)

        # return to the caller
        return LoggerWrapper(logger)
