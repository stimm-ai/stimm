"""
Environment detection and service configuration for dual-mode operation.
Handles localhost vs container name resolution for different services.
"""

import os
from typing import Dict, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class EnvironmentConfig:
    """Configuration manager loading variables from .env file"""

    def __init__(self):
        self._setup_service_urls()

    def _setup_service_urls(self):
        """Load service URLs from environment variables"""

        # Stimm API URL
        self.stimm_api_url = os.getenv("STIMM_API_URL", "http://localhost:8001")

        # LiveKit URLs
        self.livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        self.livekit_api_url = os.getenv("LIVEKIT_API_URL", "http://localhost:7880")
        self.livekit_api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
        self.livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")

        # Database URLs
        self.database_url = os.getenv("DATABASE_URL", "postgresql://stimm_user:stimm_password@localhost:5432/stimm")

        # Qdrant URL
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

        # Redis URL
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        # Frontend URL
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    def get_service_config(self, service_name: str) -> Dict[str, str]:
        """Get configuration for a specific service"""
        configs = {
            "stimm": {"api_url": self.stimm_api_url, "health_url": f"{self.stimm_api_url}/health"},
            "livekit": {"ws_url": self.livekit_url, "api_url": self.livekit_api_url},
            "database": {"url": self.database_url},
            "qdrant": {"url": self.qdrant_url},
            "redis": {"url": self.redis_url},
            "frontend": {"url": self.frontend_url},
        }

        return configs.get(service_name, {})

    def get_all_configs(self) -> Dict[str, Dict[str, str]]:
        """Get all service configurations"""
        return {
            "stimm": self.get_service_config("stimm"),
            "livekit": self.get_service_config("livekit"),
            "database": self.get_service_config("database"),
            "qdrant": self.get_service_config("qdrant"),
            "redis": self.get_service_config("redis"),
            "frontend": self.get_service_config("frontend"),
            "metadata": {"environment": os.getenv("ENVIRONMENT", "local")},
        }

    def __str__(self) -> str:
        """String representation showing key URLs"""
        config = self.get_all_configs()
        return f"Environment: {config['metadata']['environment']}\n" + f"Stimm API: {config['stimm']['api_url']}\n" + f"LiveKit: {config['livekit']['ws_url']}"


# Global configuration instance
config = EnvironmentConfig()


def get_environment_config() -> EnvironmentConfig:
    """Get the global environment configuration instance"""
    return config


# Deprecated: is_running_in_docker is no longer needed
def is_running_in_docker() -> bool:
    """DEPRECATED: Check if currently running in Docker"""
    return os.getenv("ENVIRONMENT") == "docker"


def get_service_url(service_name: str, fallback: Optional[str] = None) -> str:
    """Get URL for a service, with optional fallback"""
    service_config = config.get_service_config(service_name)

    # Look for URL in different possible keys
    url_keys = ["url", "api_url", "ws_url"]
    for key in url_keys:
        if key in service_config:
            return service_config[key]

    # Return fallback if no URL found
    return fallback or f"Unknown service: {service_name}"


# Convenience functions for common services
def get_livekit_url() -> str:
    """Get LiveKit WebSocket URL"""
    return config.livekit_url


def get_stimm_api_url() -> str:
    """Get Stimm API URL"""
    return config.stimm_api_url


def get_database_url() -> str:
    """Get database connection URL"""
    return config.database_url


def get_redis_url() -> str:
    """Get Redis connection URL"""
    return config.redis_url


def get_qdrant_url() -> str:
    """Get Qdrant connection URL"""
    return config.qdrant_url
