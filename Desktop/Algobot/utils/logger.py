import logging
import sys
import os
import json
from logging.handlers import RotatingFileHandler

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Configurable log format
    log_format = os.environ.get('LOG_FORMAT', 'plain')  # 'json' or 'plain'
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    log_file = os.environ.get('LOG_FILE', f'{name}.log')
    max_bytes = int(os.environ.get('LOG_MAX_BYTES', 2 * 1024 * 1024))  # 2MB
    backup_count = int(os.environ.get('LOG_BACKUP_COUNT', 5))

    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    if log_format == 'json':
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Rotating file handler
    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.propagate = False
    return logger 