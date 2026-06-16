#!/usr/bin/env bash
# Serve the merged exp3 model as an OpenAI-compatible endpoint for the demo.
# Reuses the exact flags proven in src/toolcall_lm/eval/taubench_runner.py
# (Qwen3 emits Hermes-style <tool_call> JSON → --tool-call-parser hermes).
#
# Needs the GPU free (it's busy while exp5 synthetic gen runs).
#
# Usage:
#   ./demo/serve_demo.sh                 # serves outputs/merged_toolmind_exp3_final on :8765
#   MODEL=/path/to/other_merged ./demo/serve_demo.sh
#   PORT=8001 ./demo/serve_demo.sh
set -euo pipefail

VENV=/home/team-a/Desktop/ToolCallLM_finetune/.venv
REPO=/home/team-a/Desktop/ToolCallLM_finetune/ToolCallLM
MODEL=${MODEL:-$REPO/outputs/merged_toolmind_exp3_final}
PORT=${PORT:-8765}

# shellcheck disable=SC1091
source "$VENV/bin/activate"
export PATH="$VENV/bin:/usr/local/cuda/bin:$PATH"

exec vllm serve "$MODEL" \
  --served-model-name exp3 \
  --port "$PORT" \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --trust-remote-code \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
