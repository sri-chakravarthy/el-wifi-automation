import logging
import os
import os.path
from pathlib import Path
# Create a logger
logger = logging.getLogger("my_logger")
#logging.debug('--------------------------------------------------------------------------');

# Set the log level (you can adjust this to your needs)
logger.setLevel(logging.DEBUG)

dPath = os.getcwd()
#print(dPath)

# Create a file handler
#logFilePath = "/opt/adapter/log/SevOne-el-sevone-ingest-apiv3.log"
logFilePath = "log/SevOne-el-sevone-wifi-automation.log"
file_handler = logging.FileHandler(logFilePath)


path = Path(logFilePath)
path.touch()

# Create a formatter with your desired log format
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the file handler to the log
logger.addHandler(file_handler)
