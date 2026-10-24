#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    message='Se necesita Python 3.8 o posterior. Instálalo desde las herramientas de tu distribución y vuelve a abrir este instalador.'
    if command -v kdialog >/dev/null 2>&1; then
        kdialog --error "$message" --title 'DBZK_Fix'
    elif command -v zenity >/dev/null 2>&1; then
        zenity --error --text="$message" --title='DBZK_Fix'
    fi
    printf '%s\n' "$message" >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))'; then
    printf '%s\n' 'Se necesita Python 3.8 o posterior.' >&2
    exit 1
fi
exec python3 "$package_dir/install.py" "$@"
