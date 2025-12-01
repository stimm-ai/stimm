#!/bin/bash

# Script de test pour la migration uv
set -e

echo "🚀 Test de migration pip -> uv"
echo "================================"

# Vérifier que Docker est disponible
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé ou n'est pas dans le PATH"
    exit 1
fi

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "src/requirements.txt" ]; then
    echo "❌ Veuillez exécuter ce script depuis la racine du projet"
    exit 1
fi

echo "✅ Environnement vérifié"

# Test de compatibilité Python
echo ""
echo "🧪 Test de compatibilité Python..."
python test_uv_compatibility.py

# Build de test avec uv
echo ""
echo "🐳 Build Docker avec uv..."
start_time=$(date +%s)
docker build -f docker/voicebot-app/Dockerfile -t voicebot-uv-test .
end_time=$(date +%s)
uv_build_time=$((end_time - start_time))

echo "✅ Build uv terminé en ${uv_build_time} secondes"

# Test de fonctionnement basique
echo ""
echo "🔍 Test de fonctionnement basique..."
if docker run --rm -it voicebot-uv-test python -c "import fastapi; import torch; import livekit; print('✅ Import des packages critiques réussi')"; then
    echo "✅ Test d'import réussi"
else
    echo "❌ Erreur lors des imports"
    exit 1
fi

# Nettoyage
echo ""
echo "🧹 Nettoyage..."
docker rmi voicebot-uv-test

echo ""
echo "🎉 Migration uv testée avec succès !"
echo "📊 Temps de build avec uv: ${uv_build_time} secondes"
echo ""
echo "📋 Prochaines étapes:"
