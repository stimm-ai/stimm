#!/usr/bin/env python3
"""
Script de test pour vérifier la compatibilité uv avec les dépendances du projet
"""

import subprocess
import sys
import os

def test_uv_installation():
    """Test l'installation de uv"""
    print("🔧 Test d'installation de uv...")
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'uv'], 
                              capture_output=True, text=True, check=True)
        print("✅ uv installé avec succès")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur installation uv: {e}")
        return False

def test_uv_resolution():
    """Test la résolution des dépendances avec uv"""
    print("\n🔍 Test de résolution des dépendances avec uv...")
    try:
        result = subprocess.run(['uv', 'pip', 'compile', 'src/requirements.txt', '--no-header'], 
                              capture_output=True, text=True, check=True)
        print("✅ Résolution des dépendances réussie avec uv")
        print(f"📦 Nombre de packages résolus: {len(result.stdout.strip().splitlines())}")
        return True
    except Exception as e:
        print(f"❌ Erreur résolution uv: {e}")
        return False

def test_critical_packages():
    """Test l'installation des packages critiques"""
    print("\n🧪 Test des packages critiques...")
    critical_packages = [
        'torch', 'onnxruntime', 'fastapi', 'livekit', 'livekit-agents',
        'sentence-transformers', 'qdrant-client', 'aiortc'
    ]
    
    for package in critical_packages:
        try:
            result = subprocess.run(['uv', 'pip', 'install', '--dry-run', package], 
                                  capture_output=True, text=True, check=True)
            print(f"✅ {package} - compatible avec uv")
        except Exception as e:
            print(f"❌ {package} - problème potentiel: {e}")

def main():
    print("🚀 Test de compatibilité uv pour VoiceBot")
    print("=" * 50)
    
    # Vérifier que nous sommes dans le bon répertoire
    if not os.path.exists('src/requirements.txt'):
        print("❌ Veuillez exécuter ce script depuis la racine du projet")
        sys.exit(1)
    
    # Exécuter les tests
    uv_ok = test_uv_installation()
    resolution_ok = test_uv_resolution()
    test_critical_packages()
    
    print("\n" + "=" * 50)
    if uv_ok and resolution_ok:
        print("🎉 Tous les tests sont passés ! uv est compatible avec votre projet.")
        print("\n📋 Prochaines étapes:")
        print("1. Construire l'image Docker avec le nouveau Dockerfile")
        print("2. Tester le fonctionnement de l'application")
        print("3. Profiter des builds plus rapides !")
    else:
        print("⚠️  Certains tests ont échoué. Vérifiez les dépendances problématiques.")

if __name__ == "__main__":
    main()