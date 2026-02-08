#!/bin/bash
# ThoughtVault auto-indexer - watches for .md file changes and re-indexes

WATCH_DIR="${1:-$HOME/documents}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEBOUNCE_SECONDS=30
LAST_INDEX=0

echo "ThoughtVault auto-indexer starting..."
echo "Watching: $WATCH_DIR"
echo "Debounce: ${DEBOUNCE_SECONDS}s"

reindex() {
    NOW=$(date +%s)
    ELAPSED=$((NOW - LAST_INDEX))
    
    if [ $ELAPSED -ge $DEBOUNCE_SECONDS ]; then
        echo "[$(date -Iseconds)] Change detected, re-indexing..."
        cd "$SCRIPT_DIR" && python3 index.py "$WATCH_DIR" 2>&1 | tail -1
        LAST_INDEX=$NOW
    else
        echo "[$(date -Iseconds)] Change detected, debouncing (${ELAPSED}s < ${DEBOUNCE_SECONDS}s)"
    fi
}

# Watch for create, modify, delete, move events on .md files
inotifywait -m -r -e create -e modify -e delete -e move \
    --include '.*\.md$' \
    "$WATCH_DIR" 2>/dev/null | while read -r directory event filename; do
    reindex
done
