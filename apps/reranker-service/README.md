# Reranker Service

Cross-encoder reranking microservice (Phase 3). Scores query–document pairs via **ONNX Runtime** and returns reordered candidate IDs.

Implementation: `src/retrieval_engine/reranker_service/`

## GPU stack (same family as embed — not PyTorch)

| Component | GPU stack |
|-----------|-----------|
| **Embed** (`uv run embed`) | FastEmbed + `onnxruntime-gpu` (CUDA 12 index) + `nvidia-cudnn-cu12` |
| **Reranker** (`uv run serve-reranker`) | ONNX cross-encoder + `onnxruntime-gpu` (same CUDA 12 index) + `nvidia-cudnn-cu12` |

**Do not use sentence-transformers/PyTorch for reranking on Windows** — `import sentence_transformers` hard-crashes (access violation) on this machine, the same reason embed moved to FastEmbed/ONNX.

Default ONNX model: `temsa/ms-marco-MiniLM-L-6-v2-onnx-cpu-qint8` (upstream: `cross-encoder/ms-marco-MiniLM-L-6-v2`). Runs on GPU via `CUDAExecutionProvider` when `RERANKER_DEVICE=cuda`.

Shared runtime fixes (from embed): CUDA 12 `onnxruntime-gpu` index, `nvidia-cudnn-cu12`, CPU onnxruntime blocked, `prepare_gpu_runtime()` PATH prep.

Verify:

```bash
curl http://localhost:8001/health
# {"backend":"onnx","device":"CUDAExecutionProvider",...}
```

## Run locally

```bash
uv sync --all-extras
uv pip uninstall onnxruntime   # if CPU wheel shadows GPU (fastembed #608)
uv run serve-reranker
```

Stop `serve-reranker` before `uv sync` on Windows (file lock on scripts).

## Docker

```bash
docker compose -f infra/docker/compose.yml up -d reranker
```

## Tracing

Jaeger UI: http://localhost:16686
