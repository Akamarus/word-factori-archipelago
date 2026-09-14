#!/usr/bin/env bash
set -eu
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3.12 or newer is required. Install it using your distribution instructions.' >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    printf '%s\n' 'Python 3.12 or newer is required.' >&2
    exit 1
fi
script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_directory/tools/install_linux.py" "$@"
