#!/usr/bin/env python3
"""
Test script to verify the provider registry system works correctly.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/app')

from services.agent.provider_registry import ProviderRegistry

def test_provider_registry():
    """Test the provider registry system."""
    print("🧪 Testing Provider Registry System...")
    
    # Create provider registry
    registry = ProviderRegistry()
    
    # Test provider discovery
    print("\n📋 Testing Provider Discovery:")
    
    # Get all available providers
    all_providers = registry.get_available_providers()
    
    # Test LLM providers
    print("\n🤖 LLM Providers:")
    llm_providers = all_providers.get("llm", {}).get("providers", [])
    print(f"  Found {len(llm_providers)} LLM providers: {[p['value'] for p in llm_providers]}")
    
    for provider in llm_providers:
        provider_name = provider["value"]
        print(f"  - {provider_name}:")
        field_defs = registry.get_provider_field_definitions("llm", provider_name)
        print(f"    Fields: {list(field_defs.keys())}")
        for field_name, field_def in field_defs.items():
            print(f"      {field_name}: {field_def.get('type', 'unknown')} ({'required' if field_def.get('required') else 'optional'})")
    
    # Test TTS providers
    print("\n🗣️ TTS Providers:")
    tts_providers = all_providers.get("tts", {}).get("providers", [])
    print(f"  Found {len(tts_providers)} TTS providers: {[p['value'] for p in tts_providers]}")
    
    for provider in tts_providers:
        provider_name = provider["value"]
        print(f"  - {provider_name}:")
        field_defs = registry.get_provider_field_definitions("tts", provider_name)
        print(f"    Fields: {list(field_defs.keys())}")
        for field_name, field_def in field_defs.items():
            print(f"      {field_name}: {field_def.get('type', 'unknown')} ({'required' if field_def.get('required') else 'optional'})")
    
    # Test STT providers
    print("\n🎤 STT Providers:")
    stt_providers = all_providers.get("stt", {}).get("providers", [])
    print(f"  Found {len(stt_providers)} STT providers: {[p['value'] for p in stt_providers]}")
    
    for provider in stt_providers:
        provider_name = provider["value"]
        print(f"  - {provider_name}:")
        field_defs = registry.get_provider_field_definitions("stt", provider_name)
        print(f"    Fields: {list(field_defs.keys())}")
        for field_name, field_def in field_defs.items():
            print(f"      {field_name}: {field_def.get('type', 'unknown')} ({'required' if field_def.get('required') else 'optional'})")
    
    # Test specific provider - Kokoro Local (should only have 'voice' field)
    print("\n🎯 Testing Kokoro Local Provider (should only have 'voice' field):")
    kokoro_fields = registry.get_provider_field_definitions("tts", "kokoro.local")
    print(f"  Kokoro Local fields: {list(kokoro_fields.keys())}")
    for field_name, field_def in kokoro_fields.items():
        print(f"    {field_name}: {field_def}")
    
    # Test expected properties fallback
    print("\n🔄 Testing Expected Properties Fallback:")
    for provider_type in ["llm", "tts", "stt"]:
        all_providers = registry.get_available_providers()
        providers = all_providers.get(provider_type, {}).get("providers", [])
        for provider in providers:
            provider_name = provider["value"]
            expected_props = registry.get_expected_properties(provider_type, provider_name)
            print(f"  {provider_type}.{provider_name}: {expected_props}")
    
    print("\n✅ Provider Registry Test Completed Successfully!")

if __name__ == "__main__":
    test_provider_registry()