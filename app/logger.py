import logging
import json
from datetime import datetime
import os

# Setup structured logger
log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(log_file),
    ]
)
logger = logging.getLogger("jarvis")

def log_action(action: str, details: dict):
    # Prevent logging sensitive keys
    safe_details = {k: v for k, v in details.items() if "password" not in k.lower() and "secret" not in k.lower()}
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": safe_details
    }
    logger.info(json.dumps(log_entry))
