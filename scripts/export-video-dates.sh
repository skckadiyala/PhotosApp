#!/usr/bin/env bash
# export-video-dates.sh
#
# Run this on your macOS host BEFORE using "Refresh Video Metadata" in the app.
# It reads the true APFS creation date (st_birthtime) for every video file and
# writes a JSON manifest to $HOST_PHOTOS_DIR/.video_creation_dates.json
# which the backend reads when refreshing video metadata.
#
# Usage:
#   ./scripts/export-video-dates.sh
#   or with an explicit photos directory:
#   ./scripts/export-video-dates.sh "/path/to/photos"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

# Read HOST_PHOTOS_DIR from .env without sourcing (handles spaces in paths)
if [[ -z "${HOST_PHOTOS_DIR:-}" && -f "$ENV_FILE" ]]; then
  HOST_PHOTOS_DIR=$(grep '^HOST_PHOTOS_DIR=' "$ENV_FILE" | head -1 | cut -d= -f2-)
fi

PHOTOS_DIR="${1:-${HOST_PHOTOS_DIR:-}}"

if [[ -z "$PHOTOS_DIR" ]]; then
  echo "ERROR: Photos directory not found."
  echo "Either set HOST_PHOTOS_DIR in .env or pass it as the first argument:"
  echo "  $0 \"/path/to/your/photos\""
  exit 1
fi

if [[ ! -d "$PHOTOS_DIR" ]]; then
  echo "ERROR: Directory does not exist: $PHOTOS_DIR"
  exit 1
fi

OUTPUT_FILE="$PHOTOS_DIR/.video_creation_dates.json"
echo "Scanning: $PHOTOS_DIR"
echo "Output  : $OUTPUT_FILE"

python3 - "$PHOTOS_DIR" "$OUTPUT_FILE" << 'PYEOF'
import os
import sys
import json
from datetime import datetime

photos_dir = sys.argv[1]
output_file = sys.argv[2]

VIDEO_EXTS = {'.mov', '.mp4', '.m4v', '.avi', '.mkv', '.webm', '.3gp'}

dates = {}
count = 0

for dirpath, _dirs, files in os.walk(photos_dir):
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in VIDEO_EXTS:
            continue
        abs_path = os.path.join(dirpath, fname)
        rel_path = os.path.relpath(abs_path, photos_dir)
        try:
            st = os.stat(abs_path)
            # st_birthtime is the APFS creation date — available on macOS only
            birthtime = getattr(st, 'st_birthtime', None)
            if birthtime and birthtime > 0:
                dt = datetime.fromtimestamp(birthtime)
                # Sanity check: must be a plausible date (after 2000, not in the future)
                if 2000 <= dt.year <= 2100:
                    dates[rel_path] = dt.strftime('%Y-%m-%dT%H:%M:%S')
                    count += 1
                    print(f"  {rel_path}: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"  WARNING: Could not stat {rel_path}: {e}", file=sys.stderr)

with open(output_file, 'w') as f:
    json.dump(dates, f, indent=2)

print(f"\nDone. Exported creation dates for {count} video(s) → {output_file}")
PYEOF
