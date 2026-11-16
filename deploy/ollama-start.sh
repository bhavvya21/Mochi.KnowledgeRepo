#!/bin/sh
set -eu
ollama serve &
server_pid=$!
trap 'kill "$server_pid"; wait "$server_pid"' TERM INT
until ollama list >/dev/null 2>&1; do sleep 2; done
ollama pull "${OLLAMA_MODEL:-qwen2.5:3b}"
if [ -n "${OLLAMA_VISION_MODEL:-}" ]; then ollama pull "$OLLAMA_VISION_MODEL"; fi
wait "$server_pid"
