"""
Unit tests for environment configuration.

These tests verify that the EnvironmentConfig class correctly loads
and manages service URLs and configuration.
"""

import pytest
import os
from unittest.mock import patch


@pytest.mark.unit
class TestEnvironmentConfig:
    """Test suite for environment configuration functionality."""
    
    def test_environment_config_initialization(self):
        """Test that EnvironmentConfig initializes with default values."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        
        # Should have service URLs set
        assert hasattr(config, 'stimm_api_url')
        assert hasattr(config, 'livekit_url')
        assert hasattr(config, 'database_url')
        assert hasattr(config, 'qdrant_url')
        assert hasattr(config, 'redis_url')
        assert hasattr(config, 'frontend_url')
    
    def test_default_service_urls(self):
        """Test that default service URLs are set correctly."""
        from environment_config import EnvironmentConfig
        
        with patch.dict(os.environ, {}, clear=True):
            config = EnvironmentConfig()
            
            # Verify defaults
            assert "localhost" in config.stimm_api_url
            assert "localhost" in config.livekit_url
            assert "localhost" in config.database_url
            assert "localhost" in config.qdrant_url
            assert "localhost" in config.redis_url
    
    @patch.dict(os.environ, {
        "STIMM_API_URL": "http://custom-api:9000",
        "LIVEKIT_URL": "ws://custom-livekit:7000"
    })
    def test_environment_variable_overrides(self):
        """Test that environment variables override defaults."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        
        assert config.stimm_api_url == "http://custom-api:9000"
        assert config.livekit_url == "ws://custom-livekit:7000"
    
    def test_get_service_config_voicebot(self):
        """Test getting VoiceBot service configuration."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        voicebot_config = config.get_service_config("stimm")
        
        assert isinstance(voicebot_config, dict)
        assert "api_url" in voicebot_config
        assert "health_url" in voicebot_config
        assert "/health" in voicebot_config["health_url"]
    
    def test_get_service_config_livekit(self):
        """Test getting LiveKit service configuration."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        livekit_config = config.get_service_config("livekit")
        
        assert isinstance(livekit_config, dict)
        assert "ws_url" in livekit_config
        assert "api_url" in livekit_config
    
    def test_get_service_config_database(self):
        """Test getting database service configuration."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        db_config = config.get_service_config("database")
        
        assert isinstance(db_config, dict)
        assert "url" in db_config
        assert "postgresql" in db_config["url"]
    
    def test_get_service_config_unknown(self):
        """Test getting configuration for unknown service."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        unknown_config = config.get_service_config("unknown_service")
        
        # Should return empty dict for unknown service
        assert unknown_config == {}
    
    def test_get_all_configs(self):
        """Test getting all service configurations."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        all_configs = config.get_all_configs()
        
        assert isinstance(all_configs, dict)
        
        # Should contain all services
        expected_services = ["stimm", "livekit", "database", "qdrant", "redis", "frontend"]
        for service in expected_services:
            assert service in all_configs
        
        # Should contain metadata
        assert "metadata" in all_configs
        assert "environment" in all_configs["metadata"]
    
    def test_config_str_representation(self):
        """Test string representation of config."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        config_str = str(config)
        
        assert isinstance(config_str, str)
        assert "Environment:" in config_str
        assert "Stimm API:" in config_str
        assert "LiveKit:" in config_str
    
    def test_global_config_instance(self):
        """Test that global config instance is available."""
        from environment_config import config
        
        assert config is not None
        assert hasattr(config, 'stimm_api_url')
    
    def test_get_environment_config_function(self):
        """Test get_environment_config() function."""
        from environment_config import get_environment_config, config
        
        retrieved_config = get_environment_config()
        
        # Should return the global instance
        assert retrieved_config is config
    
    def test_get_service_url_function(self):
        """Test get_service_url() convenience function."""
        from environment_config import get_service_url
        
        voicebot_url = get_service_url("stimm")
        
        assert isinstance(voicebot_url, str)
        # Should return one of the URL fields
        assert voicebot_url != f"Unknown service: stimm"
    
    def test_get_service_url_with_fallback(self):
        """Test get_service_url() with fallback."""
        from environment_config import get_service_url
        
        fallback_url = "http://fallback:8888"
        url = get_service_url("unknown_service", fallback=fallback_url)
        
        assert url == fallback_url
    
    def test_convenience_functions(self):
        """Test all convenience functions."""
        from environment_config import (
            get_livekit_url,
            get_stimm_api_url,
            get_database_url,
            get_redis_url,
            get_qdrant_url
        )
        
        # All should return strings
        assert isinstance(get_livekit_url(), str)
        assert isinstance(get_stimm_api_url(), str)
        assert isinstance(get_database_url(), str)
        assert isinstance(get_redis_url(), str)
        assert isinstance(get_qdrant_url(), str)
    
    def test_livekit_credentials(self):
        """Test that LiveKit credentials are loaded."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        
        assert hasattr(config, 'livekit_api_key')
        assert hasattr(config, 'livekit_api_secret')
        assert config.livekit_api_key is not None
        assert config.livekit_api_secret is not None
    
    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_environment_metadata(self):
        """Test that environment metadata is included."""
        from environment_config import EnvironmentConfig
        
        config = EnvironmentConfig()
        all_configs = config.get_all_configs()
        
        assert all_configs["metadata"]["environment"] == "production"
    
    def test_is_running_in_docker_deprecated(self):
        """Test deprecated is_running_in_docker function."""
        from environment_config import is_running_in_docker
        
        # Should return a boolean
        result = is_running_in_docker()
        assert isinstance(result, bool)
