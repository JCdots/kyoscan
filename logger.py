import logging
from logging.handlers import TimedRotatingFileHandler

handler = TimedRotatingFileHandler(
    filename='/logs/app_log.txt',
    when='midnight',
    interval=7,
    backupCount=30,
    encoding='utf-8'
)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger('kyoscan')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

def get_logger() -> logging.Logger:
    """Returns the configured logger instance."""
    return logger