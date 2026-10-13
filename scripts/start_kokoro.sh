#!/bin/bash
# Start Kokoro TTS (native, CPU) if it isn't already running.
KOKORO_DIR="$HOME/zyp/kokoro-fastapi-local"
LOG="$HOME/zyp/state/kokoro.log"

if curl -s -m 2 -o /dev/null http://localhost:8880/docs; then
    echo "Kokoro already running"
    exit 0
fi

mkdir -p "$HOME/zyp/state"
cd "$KOKORO_DIR" || { echo "Kokoro folder not found"; exit 1; }
export PATH="$HOME/.local/bin:$PATH"   # uv usually lives here
unset VIRTUAL_ENV                      # let uv use Kokoro's own .venv, not the Zyphos one

# OMP_NUM_THREADS=6: all 16 threads was ~10x slower (see timing tests)
OMP_NUM_THREADS=6 MODEL_DIR=src/models VOICES_DIR=src/voices/v1_0 \
  nohup uv run --no-sync uvicorn api.src.main:app --host 0.0.0.0 --port 8880 \
  > "$LOG" 2>&1 &

echo -n "Kokoro starting"
for i in $(seq 1 60); do
    if curl -s -m 2 -o /dev/null http://localhost:8880/docs; then
        echo " - ready"
        exit 0
    fi
    echo -n "."
    sleep 1
done
echo " - not ready after 60s, check $LOG"
exit 1
