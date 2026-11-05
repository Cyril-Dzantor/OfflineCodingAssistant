# assistant/utils/logger.py

import logging
import sys

def setup_logger(name: str = "Assistant"):
    """
    Sets up a simple logger that outputs to the console.
    We can easily expand this to write to a file later if needed.
    """
    logger = logging.getLogger(name)
    
    # Only configure if the logger doesn't already have handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create formatter and add it to the handler
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(formatter)
        
        # Add handler to the logger
        logger.addHandler(console_handler)
        
    return logger

# Create a default logger instance to be imported across the app
app_logger = setup_logger()
