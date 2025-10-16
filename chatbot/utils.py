import os
import time

from chatbot.logging_conf import logger


def format_phone_number(phone_number: str) -> str:
    phone_number = "".join(filter(str.isdigit, phone_number))
    formatted_phone_number = f"+{phone_number[:2]} {phone_number[2:5]} {phone_number[5:7]} {phone_number[7:9]} {phone_number[9:]}"
    logger.debug(f"{phone_number} formateado a: {formatted_phone_number}")
    return formatted_phone_number


def create_dirs():
    """Create necessary directories for the application.
    
    Creates static, static/images, and static/reports directories
    if they don't exist. Uses exist_ok=True to avoid errors
    if directories already exist.
    """
    directories = [
        "static",
        "static/images", 
        "static/reports"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            if not os.path.exists(directory):
                logger.error(f"Failed to create directory: {directory}")
            else:
                logger.info(f"Directory '{directory}' ensured to exist")
        except OSError as e:
            logger.error(f"Error creating directory '{directory}': {e}")
            raise RuntimeError(f"Could not create required directory '{directory}': {e}")


def check_time(last_time):
    performance = time.time() - last_time
    if performance > 25:
        logger.warning(f"Performance of the API: {performance}")
    else:
        logger.debug(f"Performance of the API: {performance}")
