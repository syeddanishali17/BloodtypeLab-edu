#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ "$#" -lt 1 ]; then
  echo 'Usage: sh run_java.sh NEW_OUTPUT_FOLDER [REPLICATES=20] [SEED=10001]' >&2
  exit 2
fi
exec java BloodTypeModel.java . "$1" "${2:-20}" "${3:-10001}"
