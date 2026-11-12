#!/usr/bin/env bash
set -euo pipefail
packages=()
for command in "$@"; do
  if ! command -v "$command" >/dev/null 2>&1; then
    packages+=("$command")
  fi
done
if [ "${#packages[@]}" -eq 0 ]; then
  echo "Required system tools are already installed."
  exit 0
fi
options=(-o Acquire::Retries=1 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 -o APT::Update::Error-Mode=any)
for attempt in 1 2 3; do
  if timeout 180 sudo apt-get "${options[@]}" update &&
     timeout 180 sudo apt-get "${options[@]}" install --no-install-recommends -y "${packages[@]}"; then
    exit 0
  fi
  if [ "$attempt" -lt 3 ]; then sleep "$((attempt * 5))"; fi
done
echo "::error::System package installation failed after three bounded attempts."
exit 1
