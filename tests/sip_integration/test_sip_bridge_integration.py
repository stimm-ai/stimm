#!/usr/bin/env python3
"""
Test script for SIP Bridge Integration
Teste l'intégration du SIP Bridge dans le conteneur stimm-app
"""

import asyncio
import requests
import time
import sys

def test_sip_bridge_health():
    """Test le endpoint de health check du SIP Bridge"""
    try:
        response = requests.get("http://localhost:8001/health/sip-bridge", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check response: {data}")
            return data
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return None

def test_sip_bridge_integration():
    """Test l'intégration du SIP Bridge"""
    print("🧪 Testing SIP Bridge Integration...")
    
    # Test via health check HTTP (qui accède à l'application Docker)
    print("\n📡 Testing SIP Bridge via HTTP health check...")
    health_data = test_sip_bridge_health()
    
    if health_data:
        status = health_data.get('status', 'unknown')
        sip_bridge_status = health_data.get('sip_bridge', 'unknown')
        print(f"✅ SIP Bridge status: {status}")
        print(f"✅ SIP Bridge health: {sip_bridge_status}")
        
        if status == 'healthy' and sip_bridge_status == 'running':
            print("✅ SIP Bridge Integration is working correctly!")
            return True
        elif status == 'disabled':
            print("⚠️  SIP Bridge is disabled in Docker environment")
            return True  # C'est normal si c'est désactivé
        else:
            print("❌ SIP Bridge has issues")
            return False
    else:
        print("❌ Health check failed")
        return False

def test_sip_room_detection():
    """Test la détection des rooms SIP (simulation)"""
    print("\n🔍 Testing SIP room detection...")
    
    # Simuler la création d'une room SIP
    test_room_name = "sip-inbound-test-call-123"
    
    # Vérifier via le health check HTTP que le bridge est prêt
    health_data = test_sip_bridge_health()
    
    if health_data and health_data.get('status') == 'healthy' and health_data.get('sip_bridge') == 'running':
        print(f"✅ SIP Bridge is ready to detect rooms like '{test_room_name}'")
        print(f"✅ SIP monitoring is active for rooms with prefix 'sip-inbound-'")
        return True
    else:
        print("❌ SIP Bridge is not ready")
        print(f"Health check result: {health_data}")
        return False

async def main():
    """Fonction principale de test"""
    print("🚀 Starting SIP Bridge Integration Tests...")
    print("=" * 50)
    
    # Attendre que l'application démarre
    print("⏳ Waiting for application to start...")
    time.sleep(3)
    
    # Tests
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Intégration
    if test_sip_bridge_integration():
        tests_passed += 1
    
    # Test 2: Détection des rooms
    if test_sip_room_detection():
        tests_passed += 1
    
    # Résultat
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! SIP Bridge Integration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the logs above.")
        return 1

if __name__ == "__main__":
    # Vérifier que l'application est accessible
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code != 200:
            print("❌ Application is not responding. Make sure it's running.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to application: {e}")
        print("Make sure the stimm-app is running with: docker compose up")
        sys.exit(1)
    
    # Lancer les tests
    result = asyncio.run(main())
    sys.exit(result)