import json
import logging
from app.core.logging import configure_logging, get_logger
from app.core.config import settings

def test_configure_logging_development(monkeypatch, capsys):
    monkeypatch.setattr(settings, "app_env", "development")
    configure_logging()
    logger = get_logger("test_dev")
    logger.info("Testing dev log")
    
    # Actually pytest caplog captures standard logging, but we can verify that the root logger 
    # has standard stream handler and a basic formatter (not JSON)
    root_logger = logging.getLogger()
    assert len(root_logger.handlers) > 0
    formatter = root_logger.handlers[0].formatter
    assert not hasattr(formatter, 'exc_info_key') # JSONFormatter has specific logic, this is basic formatter
    # Can also check string representation of formatter
    assert "asctime" in formatter._fmt or "message" in formatter._fmt

def test_configure_logging_production(monkeypatch, capsys):
    monkeypatch.setattr(settings, "app_env", "production")
    configure_logging()
    logger = get_logger("test_prod")
    logger.info("Testing prod log")
    
    # In production, JSONFormatter should be used
    root_logger = logging.getLogger()
    assert len(root_logger.handlers) > 0
    formatter = root_logger.handlers[0].formatter
    # We can invoke format directly to test output format is valid JSON
    record = logging.LogRecord("test_prod", logging.INFO, pathname="", lineno=1, msg="Testing prod log", args=(), exc_info=None)
    
    formatted_output = formatter.format(record)
    
    # It should parse as JSON
    parsed = json.loads(formatted_output)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Testing prod log"
    assert parsed["name"] == "test_prod"
    assert "timestamp" in parsed

def test_get_logger():
    logger = get_logger("my_custom_logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "my_custom_logger"
