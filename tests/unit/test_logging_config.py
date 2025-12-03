"""
Unit tests for logging configuration.

These tests verify that logging is configured correctly with different
verbosity levels and environment variables.
"""

import pytest
import logging
import os
from unittest.mock import patch


@pytest.mark.unit
class TestLoggingConfig:
    """Test suite for logging configuration functionality."""
    
    def setup_method(self):
        """Reset logging configuration before each test."""
        # Clear all handlers to start fresh
        logging.root.handlers = []
        logging.root.setLevel(logging.WARNING)
    
    def test_configure_logging_non_verbose(self):
        """Test logging configuration with verbose=False."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=False)
        
        # Root logger should be WARNING level
        assert logging.root.level == logging.WARNING
        
        # App loggers should be INFO level
        app_logger = logging.getLogger("src")
        assert app_logger.level == logging.INFO
    
    def test_configure_logging_verbose(self):
        """Test logging configuration with verbose=True."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=True)
        
        # Root logger should be INFO level in verbose mode
        assert logging.root.level == logging.INFO
        
        # App loggers should be DEBUG level
        app_logger = logging.getLogger("src")
        assert app_logger.level == logging.DEBUG
    
    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_log_level_env_variable(self):
        """Test that LOG_LEVEL environment variable sets verbose mode."""
        from utils.logging_config import configure_logging
        
        # Call without verbose flag, but env var should activate it
        configure_logging(verbose=False)
        
        # Should behave as if verbose=True due to env var
        app_logger = logging.getLogger("src")
        assert app_logger.level == logging.DEBUG
    
    def test_asyncio_logger_suppressed(self):
        """Test that asyncio logger is set to WARNING."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=True)
        
        asyncio_logger = logging.getLogger("asyncio")
        assert asyncio_logger.level == logging.WARNING
    
    def test_livekit_logger_in_verbose_mode(self):
        """Test that LiveKit logger is INFO in verbose mode."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=True)
        
        livekit_logger = logging.getLogger("livekit")
        assert livekit_logger.level == logging.INFO
    
    def test_aiohttp_logger_in_verbose_mode(self):
        """Test that aiohttp logger is INFO in verbose mode."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=True)
        
        aiohttp_logger = logging.getLogger("aiohttp")
        assert aiohttp_logger.level == logging.INFO
    
    def test_application_logger_names(self):
        """Test that all application loggers are configured."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=True)
        
        app_logger_names = ["src", "services", "cli", "agent-worker", "__main__"]
        
        for logger_name in app_logger_names:
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.DEBUG
            assert logger.propagate is True
    
    def test_logging_handlers_configured(self):
        """Test that logging handlers are present."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=False)
        
        # Root logger should have handlers
        assert len(logging.root.handlers) > 0
        
        # Should have a StreamHandler
        has_stream_handler = any(
            isinstance(h, logging.StreamHandler) 
            for h in logging.root.handlers
        )
        assert has_stream_handler
    
    def test_logging_format(self):
        """Test that logging format is configured."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=False)
        
        # Check that handlers have formatters
        for handler in logging.root.handlers:
            assert handler.formatter is not None
            
            # Check format includes expected fields
            format_str = handler.formatter._fmt
            assert "asctime" in format_str
            assert "name" in format_str
            assert "levelname" in format_str
            assert "message" in format_str
    
    @patch.dict(os.environ, {"LOG_LEVEL": "INFO"})
    def test_log_level_env_not_debug(self):
        """Test that LOG_LEVEL=INFO doesn't activate verbose mode."""
        from utils.logging_config import configure_logging
        
        configure_logging(verbose=False)
        
        # Should remain non-verbose
        app_logger = logging.getLogger("src")
        assert app_logger.level == logging.INFO
    
    def test_multiple_configure_calls(self):
        """Test that configure_logging can be called multiple times."""
        from utils.logging_config import configure_logging
        
        # First call
        configure_logging(verbose=False)
        first_level = logging.getLogger("src").level
        
        # Second call with different setting
        configure_logging(verbose=True)
        second_level = logging.getLogger("src").level
        
        # Levels should be different
        assert first_level != second_level
        assert second_level == logging.DEBUG
