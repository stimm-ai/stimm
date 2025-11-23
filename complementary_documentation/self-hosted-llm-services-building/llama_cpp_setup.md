# Llama.cpp Setup and Quantized Model Deployment

This guide walks through the process we used to run `mistralai/Ministral-8B-Instruct-2410` on an RTX 4070 Ti with llama.cpp. It covers building llama.cpp with CUDA, converting and quantizing the Hugging Face checkpoint to GGUF, running the model locally, and packaging it for Docker Compose.

## 1. Prerequisites

- Ubuntu/WSL environment with CUDA 12.4 runtime and the NVIDIA driver that powers your RTX 4070 Ti.
- `git`, `cmake`, `build-essential`, `python3`, `python3-venv`, `pip`.
- Hugging Face token with access to the target model (`export HF_TOKEN=...`).

The examples assume the repository root is `~/repos/voicebot`.

## 2. Clone llama.cpp and build with CUDA support

```bash
cd ~/repos/voicebot
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -S . -B build -DLLAMA_CUDA=ON -DLLAMA_BUILD_SERVER=ON
cmake --build build --config Release -j"$(nproc)"
```

The binaries are produced in `build/bin/` (e.g. `llama-cli`, `llama-server`, `llama-quantize`).

## 3. Prepare the Python environment for conversion

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/requirements-convert_hf_to_gguf.txt
```

> The conversion requirements install a specific transformers fork (`v4.56.0-Embedding-Gemma-preview`), `mistral-common`, `gguf`, etc. Installing inside a venv keeps them isolated.

## 4. Download the Hugging Face checkpoint

```bash
cd ~/repos/voicebot
mkdir -p qtNim/hf  # reuse existing directory
huggingface-cli download mistralai/Ministral-8B-Instruct-2410 \
  --token "$HF_TOKEN" \
  --local-dir qtNim/hf/Ministral-8B-Instruct-2410 \
  --local-dir-use-symlinks False
```

You should now have the original safetensors + tokenizer assets in `qtNim/hf/Ministral-8B-Instruct-2410`.

## 5. Convert to GGUF (full precision)

```bash
cd ~/repos/voicebot/llama.cpp
source .venv/bin/activate
python convert_hf_to_gguf.py \
  ~/repos/voicebot/qtNim/hf/Ministral-8B-Instruct-2410 \
  --outfile models/ministral-8b-instruct-f16.gguf \
  --outtype f16
```

This generates a ~15 GB `ministral-8b-instruct-f16.gguf` file in the `models/` directory.

## 6. Quantize to Q4_K_M

```bash
./build/bin/llama-quantize \
  models/ministral-8b-instruct-f16.gguf \
  models/ministral-8b-instruct-q4_k_m.gguf \
  Q4_K_M
```

The resulting `ministral-8b-instruct-q4_k_m.gguf` is ~4.6 GB and fits comfortably in the 12 GB VRAM of a 4070 Ti. Keep both files if you plan to produce other quantizations later.

## 7. Local inference tests

Interactive chat with colored output and full GPU offload:

```bash
./build/bin/llama-cli \
  -m models/ministral-8b-instruct-q4_k_m.gguf \
  -c 4096 --n-gpu-layers 10000 \
  --temp 0.7 --top-p 0.9 \
  --interactive-first --color
```

Abort with `Ctrl+C`. Use `--system-prompt "You are a helpful assistant."` to set a system message.

## 8. Run the HTTP server (OpenAI-compatible)

```bash
./build/bin/llama-server \
  -m models/ministral-8b-instruct-q4_k_m.gguf \
  --host 0.0.0.0 --port 8000 \
  --ctx-size 4096 --batch-size 512 \
  --n-gpu-layers 10000 --threads 8
```

Test with curl:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Bonjour !"}],"stream":false}'
```

Enable streaming (`"stream": true`) for token-by-token responses, useful in a voicebot pipeline.