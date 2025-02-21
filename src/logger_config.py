import logging
import os
import os.path
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json

# Create a logger
#file_prefix = "/app/"
file_prefix = ""
configurationFile = file_prefix + "etc/config.json"
with open(configurationFile, "r") as f:
    try:
        config = json.load(f)
    except json.decoder.JSONDecodeError as e:

        exit()
logLevel = config["LogLevel"]
maxLogFileSize=config["MaxLogFileSize"]


# Create a logger
logger = logging.getLogger("my_logger")
#logging.debug('--------------------------------------------------------------------------');

# Set the log level (you can adjust this to your needs)
#logger.setLevel(logging.DEBUG)


dPath = os.getcwd()
#print(dPath)

# Create a file handler
#logFilePath = "/app/log/ps-selfmon-last-polled.log"
logFilePath = file_prefix + "log/el-wifi-automation.log"
#file_handler = logging.FileHandler(logFilePath)
size_handler = RotatingFileHandler(logFilePath, maxBytes=int(maxLogFileSize), backupCount=10)
if 'DEBUG' in logLevel:
    size_handler.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
elif 'INFO' in logLevel:
    size_handler.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)
elif 'WARNING' in logLevel:
    size_handler.setLevel(logging.WARNING)
    logger.setLevel(logging.WARNING)
elif 'ERROR' in logLevel:
    size_handler.setLevel(logging.ERROR)
    logger.setLevel(logging.ERROR)
elif 'CRITICAL' in logLevel:
    size_handler.setLevel(logging.CRITICAL)
    logger.setLevel(logging.CRITICAL)
else:
    size_handler.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)



path = Path(logFilePath)
path.touch()
os.chmod(logFilePath, 0o777)

# Create a formatter with your desired log format
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
size_handler.setFormatter(formatter)

# Add the file handler to the log
logger.addHandler(size_handler)

