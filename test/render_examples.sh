#!/usr/bin/env zsh

# Test script for rendering flyers
# Takes content from test/content and merges it into templates
# Outputs rendered images to test/output

# Determine repo root from this script's location
script_dir=${0:a:h}
repo_root=${script_dir:h}

content_dir="$repo_root/test/content"
out_dir="$repo_root/test/output"

mkdir -p "$out_dir"

echo "Repo root: $repo_root"
echo "Content dir: $content_dir"
echo "Output dir: $out_dir"
echo ""

set -euo pipefail

# Find content YAML files and render each one
typeset -i count=0
for content_yaml in "$content_dir"/*_content.yaml; do
  base=$(basename "$content_yaml" _content.yaml)
  echo "Rendering: $base"
  
  # Extract regions path from content YAML (handle spaces in paths)
  regions_yaml=$(grep "^regions:" "$content_yaml" | sed 's/^regions: *//;s/["\047]//g')
  
  # Resolve relative path if needed
  if [[ "$regions_yaml" != /* ]]; then
    regions_yaml="$repo_root/$regions_yaml"
  fi
  
  # Output file
  out_file="$out_dir/${base}_rendered.png"
  
  # Run flyte render
  uv run flyte -r "$regions_yaml" -c "$content_yaml" -o "$out_file"
  echo "  → $out_file"
  count=$((count + 1))
done

echo ""
echo "✓ Rendered $count example(s). Outputs written to: $out_dir"
