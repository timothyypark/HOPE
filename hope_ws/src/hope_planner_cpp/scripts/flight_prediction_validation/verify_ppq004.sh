#!/usr/bin/env bash
set -euo pipefail
scripts=$(cd "$(dirname "$0")" && pwd)
output=${1:?Usage: verify_ppq004.sh NEW_ABSOLUTE_OUTPUT [--development --skip-integrated]}
shift
[[ "$output" = /* && ! -e "$output" ]] || { echo 'New absolute output required' >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1
exec "${HOPE_PPQ004_PYTHON:-python3}" "$scripts/ppq004_campaign.py" --output "$output" "$@"
