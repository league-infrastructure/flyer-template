#!/usr/bin/env zsh

# Determine repo root from this script's location
script_dir=${0:a:h}
repo_root=${script_dir:h}

examples_dir="$repo_root/examples"
out_dir="$repo_root/test/examples"

mkdir -p "$out_dir"

echo "Repo root: $repo_root"
echo "Examples dir: $examples_dir"
echo "Output dir: $out_dir"

set -euo pipefail

# Find PNG/JPEG images in examples and run the importer
typeset -i count=0
for img in "$examples_dir"/**/*(.N); do
  # Only process common image extensions
  case ${img:t} in
    *.png|*.jpg|*.jpeg) ;;
    *) continue ;;
  esac

  echo "Processing: $img"
  uv run flyte -i "$img" -o "$out_dir"
  count=$((count + 1))
done

echo "Processed $count example image(s). Outputs written to: $out_dir"
