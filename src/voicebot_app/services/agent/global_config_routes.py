"""
Global Provider Configuration Routes

API routes for managing global provider configurations that apply to all agents
of a given provider type.
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .global_config_service import GlobalConfigService, get_global_config_service
from database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/global-config", tags=["global-config"])


@router.get("/providers", response_model=List[Dict[str, Any]])
async def get_all_provider_configs(
    provider_type: str = None,
    db: Session = Depends(get_db)
):
    """Get all global provider configurations"""
    try:
        service = get_global_config_service(db)
        configs = service.get_all_provider_configs(provider_type)
        return configs
    except Exception as e:
        logger.error(f"Failed to get provider configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider configurations"
        )


@router.get("/providers/{provider_type}/{provider_name}", response_model=Dict[str, Any])
async def get_provider_config(
    provider_type: str,
    provider_name: str,
    db: Session = Depends(get_db)
):
    """Get global configuration for a specific provider"""
    try:
        service = get_global_config_service(db)
        config = service.get_provider_config(provider_type, provider_name)
        
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration not found for {provider_type}/{provider_name}"
            )
        
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider config for {provider_type}/{provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider configuration"
        )


@router.put("/providers/{provider_type}/{provider_name}", response_model=Dict[str, Any])
async def update_provider_config(
    provider_type: str,
    provider_name: str,
    settings: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Update global configuration for a specific provider"""
    try:
        service = get_global_config_service(db)
        success = service.set_provider_config(provider_type, provider_name, settings)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update configuration for {provider_type}/{provider_name}"
            )
        
        return {"message": "Configuration updated successfully", "settings": settings}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update provider config for {provider_type}/{provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update provider configuration"
        )


@router.delete("/providers/{provider_type}/{provider_name}")
async def delete_provider_config(
    provider_type: str,
    provider_name: str,
    db: Session = Depends(get_db)
):
    """Delete global configuration for a specific provider"""
    try:
        service = get_global_config_service(db)
        success = service.delete_provider_config(provider_type, provider_name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration not found for {provider_type}/{provider_name}"
            )
        
        return {"message": "Configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete provider config for {provider_type}/{provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete provider configuration"
        )


@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_provider_templates(
    provider_type: str = None,
    provider_name: str = None,
    db: Session = Depends(get_db)
):
    """Get provider setting templates"""
    try:
        service = get_global_config_service(db)
        templates = service.get_provider_templates(provider_type, provider_name)
        return templates
    except Exception as e:
        logger.error(f"Failed to get provider templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider templates"
        )


@router.post("/migrate-env", response_model=Dict[str, bool])
async def migrate_environment_variables(
    env_vars: Dict[str, str],
    db: Session = Depends(get_db)
):
    """Migrate environment variables to global configurations"""
    try:
        service = get_global_config_service(db)
        results = service.migrate_env_variables(env_vars)
        return results
    except Exception as e:
        logger.error(f"Failed to migrate environment variables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to migrate environment variables"
        )


@router.post("/initialize-templates")
async def initialize_templates(db: Session = Depends(get_db)):
    """Initialize provider setting templates in the database"""
    try:
        service = get_global_config_service(db)
        service.initialize_templates()
        return {"message": "Provider templates initialized successfully"}
    except Exception as e:
        logger.error(f"Failed to initialize templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize provider templates"
        )


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for global config service"""
    try:
        service = get_global_config_service(db)
        # Try to get a simple query to verify database connectivity
        templates = service.get_provider_templates()
        return {
            "status": "healthy",
            "database": "connected",
            "templates_count": len(templates)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Global config service is unhealthy"
        )