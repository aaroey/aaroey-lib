#!/bin/bash
set -ex

copy_images() {
  if [[ "$#" -ne 2 ]]; then
    echo 'Usage: copy_images <image_names_file> <destination_path>'
    return
  fi
  local image_names_file="$1"
  local dst="$2"
  while IFS= read -r line; do
    rsync -R "$line" "$dst"
  done < "$image_names_file"
}

copy_images "$@"
