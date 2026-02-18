# Machine Profile (Local Dev)

This file is meant to give agents the minimum hardware/software facts needed to make good tradeoffs (model choice, concurrency, timeouts).

## System
- OS: Windows 11 Pro
- CPU: Intel i5-10210U (4C/8T)
- RAM: 32 GB (31.78 GB observed)
- GPU: Intel UHD (no NVIDIA/CUDA)
- Disk: C: has limited free space (about 34 GB observed during setup)

## Toolchain
- Python: 3.11.9
- Node: 20.20.0
- Git: 2.52.0.windows.1
- Ollama: 0.14.2

## Local Models
- `phi4:latest` (about 9.1 GB): works on CPU but can be slow
- `phi3:mini` (about 2.2 GB): much faster on CPU

## Recommended Defaults For This Machine
- Prefer `ollama/phi3:mini` when iterating quickly; switch back to `ollama/phi4` for quality passes.
- Keep concurrency modest (CPU-only). Avoid running too many heavy agents in parallel if latency feels bad.

