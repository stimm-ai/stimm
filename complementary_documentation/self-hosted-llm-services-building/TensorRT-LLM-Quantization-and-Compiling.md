# A Corrected A-to-Z Guide: Running Quantized LLMs with TensorRT-LLM on an RTX 4070 Ti

This guide provides a complete, verified workflow to run a quantized Large Language Model (LLM) on an NVIDIA RTX 4070 Ti using the official TensorRT-LLM Docker container. The steps have been corrected to reflect recent changes in the toolkit's commands and to ensure a smooth process from start to finish.

## Prerequisites: Host System Setup

Before starting, ensure your host machine (the computer you are working on) is properly configured:

- **NVIDIA Driver**: Install a recent NVIDIA driver that supports your RTX 4070 Ti and the CUDA version inside the Docker container. The latest stable driver is recommended.
- **Docker Engine**: Install Docker for your operating system.
- **NVIDIA Container Toolkit**: This is essential for allowing Docker to access your GPU. Install it by following the official NVIDIA instructions for your OS. After installation, restart the Docker service.

## Step 1: Launch the Docker Environment

This command will pull the latest official TensorRT-LLM release container from NVIDIA's NGC catalog and start an interactive session. This container includes all the necessary pre-installed dependencies.

1. Open your terminal and run the following command. Important: Replace `/path/to/your/local/models` with an actual absolute path on your machine (e.g., `~/my_models` on Linux or `C:/Users/YourUser/my_models` on Windows). This directory will be used to persist your models and compiled engines.

```bash
docker run --rm -it --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 -p 8000:8000 -v /path/to/your/local/models:/models nvcr.io/nvidia/tensorrt-llm/release:latest
```

- `--gpus all`: Exposes your RTX 4070 Ti to the container.
- `--ipc=host`: Prevents potential "Bus error" issues during the build process.
- `-p 8000:8000`: Maps port 8000 from the container to your host machine for the web server.
- `-v /path/to/your/local/models:/models`: Links a host directory to `/models` inside the container. **This is crucial for saving your work.**

You will now be inside the container with a root shell prompt (e.g., `root@<container_id>:/#`).

## Step 2: Download a Compatible Model

The 12GB VRAM on the RTX 4070 Ti can be a limitation for larger models, especially during the memory-intensive build process. We encountered a memory-related bug with a 7B model, so we will proceed with a smaller model, `TinyLlama-1.1B-Chat-v1.0`, to validate the entire workflow.

First, install `git` and `git-lfs` inside the container:

```bash
apt-get update && apt-get install -y git git-lfs
```

Now, clone the model from Hugging Face into your persistent `/models` directory:

```bash
git clone https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0 /models/TinyLlama-1.1B-Chat-v1.0
```

## Step 3: Quantize the Model (INT4 AWQ)

Quantization reduces the model's memory footprint, which is essential for consumer GPUs. We will use the INT4 Activation-Aware Weight Quantization (AWQ) method.

Run the following command inside the container. This script takes the full-precision model and creates a compressed "quantized checkpoint":

```bash
python3 /app/tensorrt_llm/examples/quantization/quantize.py \
    --model_dir /models/TinyLlama-1.1B-Chat-v1.0 \
    --dtype float16 \
    --qformat int4_awq \
    --output_dir /models/tinyllama_awq_ckpt \
    --device cuda
```

- `--output_dir`: This is the corrected flag for specifying the output path.
- `--device cuda`: This flag is necessary to prevent device mismatch errors when loading the model.

Upon completion, a new directory `/models/tinyllama_awq_ckpt` will be created containing the quantized model.

## Step 4: Build the TensorRT Engine

This is the compilation step. The `trtllm-build` command takes the quantized checkpoint and creates a hyper-optimized, non-portable "engine" specifically for your RTX 4070 Ti's architecture.

```bash
trtllm-build --checkpoint_dir /models/tinyllama_awq_ckpt \
             --output_dir /models/tinyllama_engine_awq \
             --gemm_plugin float16 \
             --gpt_attention_plugin float16 \
             --max_batch_size 1 \
             --max_input_len 2048 \
             --max_seq_len 2560
```

- `--max_seq_len 2560`: This is the corrected flag, representing the sum of `--max_input_len (2048)` and the desired max output tokens (512). The old `--max_output_len` flag is no longer used.

This process will take several minutes. When it finishes, the `/models/tinyllama_engine_awq` directory will contain the final `rank0.engine` file.

## Step 5: Serve the Model

Now, we will launch the OpenAI-compatible web server using the compiled engine.

```bash
trtllm-serve /models/tinyllama_engine_awq \
             --tokenizer /models/TinyLlama-1.1B-Chat-v1.0 \
             --host 0.0.0.0
```

- The model path is now a direct argument, not behind a `--model` flag.
- The tokenizer flag is now `--tokenizer`, not `--tokenizer_dir`.
- `--host 0.0.0.0`: This is essential. It makes the server accessible from outside the Docker container, preventing "Connection reset by peer" errors.

You will see output indicating the server has started, ending with:

```
INFO: Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## Step 6: Test the Server

The server is running inside the container. To test it, open a new, separate terminal on your host machine (your main Windows, Linux, or macOS terminal) and run the following `curl` command.

```bash
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tinyllama",
    "prompt": "The capital of France is",
    "max_tokens": 20,
    "temperature": 0.5
  }'
```

You should receive a successful JSON response from the model, like this:

```json
{
  "id": "cmpl-d795b3dd921846aea613a4589a7693d5",
  "object": "text_completion",
  "created": 1759333588,
  "model": "tinyllama_engine_awq",
  "choices": [...],
  "usage": {
    "prompt_tokens": 6,
    "total_tokens": 23,
    "completion_tokens": 17
  }
}
```

Congratulations! You have successfully quantized, compiled, and served an LLM with TensorRT-LLM.