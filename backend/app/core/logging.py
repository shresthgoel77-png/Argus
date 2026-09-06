import logging
import json
import logging.config
from datetime import datetime
from app.core.config import settings

class JSONFormatter(logging.Formatter):
    """
    Format logs as structured JSON records.
    """
    def format(self, record):
        # NOTE: Be careful not to log sensitive values like credentials or PII here.
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        # Add basic exception traceback if available
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record)

def configure_logging():
    """
    Configure the root logger's output format and log level based on the environment.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # We will configure standard logging handlers
    handler = logging.StreamHandler()
    
    if settings.app_env == "development":
        # Human-readable console format in development
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # Structured JSON format in production and test
        formatter = JSONFormatter()
    
    handler.setFormatter(formatter)
    
    # Apply configuration to root logger using basicConfig
    logging.basicConfig(
        level=level,
        handlers=[handler],
        force=True  # Override any existing standard logging configuration (e.g. from uvicorn initially)
    )

def get_logger(name: str):
    """
    Return a structured logger for a given module name.
    """
    return logging.getLogger(name)
