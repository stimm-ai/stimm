# Guide Complet : Exécuter Llama 3.1 8B FP8 avec TensorRT-LLM

Ce guide fournit un flux de travail complet et vérifié pour compiler et servir un grand modèle de langage (LLM) quantisé en FP8 sur un GPU NVIDIA compatible (architecture Ada Lovelace, ex: RTX 4070 Ti), en utilisant le conteneur Docker officiel de TensorRT-LLM.

Le résultat final est un point de terminaison d'API compatible avec OpenAI, servant le modèle Llama-3.1-8B-Instruct-FP8.

## Prérequis : Configuration du Système Hôte

Avant de commencer, assurez-vous que votre machine hôte est correctement configurée :

- **Pilote NVIDIA** : Installez un pilote NVIDIA récent qui supporte votre GPU et la version de CUDA du conteneur. Le dernier pilote stable est recommandé.
- **Docker Engine** : Installez Docker pour votre système d'exploitation.
- **NVIDIA Container Toolkit** : Indispensable pour permettre à Docker d'accéder à votre GPU. Suivez les instructions officielles de NVIDIA. Redémarrez le service Docker après l'installation.

## Méthode 1 : Exécution Manuelle (Étape par Étape)

Cette méthode est utile pour comprendre chaque étape du processus.

### Étape 1 : Lancement de l'Environnement Docker

Cette commande télécharge le conteneur officiel de TensorRT-LLM, le démarre et ouvre une session interactive. Le conteneur inclut toutes les dépendances nécessaires.

**Important** : Remplacez `/path/to/your/local/models` par un chemin d'accès absolu sur votre machine (ex: `~/my_models` sur Linux). Ce répertoire persistera vos modèles et vos moteurs compilés.

```bash
docker run --rm -it --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 -p 8000:8000 -v /path/to/your/local/models:/models nvcr.io/nvidia/tensorrt-llm/release:latest
```

Vous êtes maintenant à l'intérieur du conteneur avec un prompt `root@...`.

### Étape 2 : Téléchargement du Modèle FP8

Nous allons cloner le modèle pré-quantisé en FP8 par NVIDIA depuis Hugging Face.

Installez git et git-lfs dans le conteneur :

```bash
apt-get update && apt-get install -y git git-lfs
```

Clonez le modèle :

```bash
git clone https://huggingface.co/nvidia/Llama-3.1-8B-Instruct-FP8 /models/Llama-3.1-8B-Instruct-FP8
```

### Étape 3 : Conversion au Format Checkpoint TensorRT-LLM

Le format des fichiers sur Hugging Face doit être converti en un format "checkpoint" que `trtllm-build` peut comprendre. Ce script gère la conversion tout en préservant la quantification FP8.

```bash
python3 /app/tensorrt_llm/examples/models/core/llama/convert_checkpoint.py \
        --model_dir /models/Llama-3.1-8B-Instruct-FP8/ \
        --output_dir /models/llama_3.1_8b_trtllm_ckpt_fp8/ \
        --use_fp8 \
        --fp8_kv_cache
```

### Étape 4 : Construction du Moteur TensorRT

C'est l'étape de compilation qui crée un moteur hautement optimisé pour votre GPU. C'est le processus le plus long et le plus gourmand en mémoire.

```bash
trtllm-build --checkpoint_dir /models/llama_3.1_8b_trtllm_ckpt_fp8/ \
             --output_dir /models/llama_3.1_8b_engine_fp8 \
             --gemm_plugin auto \
             --gpt_attention_plugin auto \
             --max_batch_size 1 \
             --max_input_len 2048 \
             --max_seq_len 2560
```

### Étape 5 : Démarrage du Serveur OpenAI-Compatible

Une fois le moteur construit, nous lançons le serveur web.

```bash
trtllm-serve /models/llama_3.1_8b_engine_fp8 \
             --tokenizer /models/Llama-3.1-8B-Instruct-FP8 \
             --host 0.0.0.0
```

### Étape 6 : Test de l'API

Pour tester, ouvrez un nouveau terminal sur votre machine hôte (pas dans le conteneur Docker) et exécutez la commande curl suivante.

```bash
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama_3.1_8b_engine_fp8",
    "prompt": "The capital of France is",
    "max_tokens": 50,
    "temperature": 0.5
  }'
```