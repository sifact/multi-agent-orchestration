#!/usr/bin/env bash
# Stage the Vercel deploy: copy the package and the knowledge documents, plus a copy of the
# database with the scoring answer key removed, so the public server never holds it.
# Run from anywhere; then deploy with: cd deploy/vercel && vercel deploy --prod
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
database="$root/data/generated/contoso_aero.sqlite3"

if [[ ! -f "$database" ]]; then
  echo "Dataset missing. Build it with: uv run python -m contoso_aero.data" >&2
  exit 1
fi

rm -rf "$here/src" "$here/data"
mkdir -p "$here/src" "$here/data/generated"
cp -R "$root/src/contoso_aero" "$here/src/"
find "$here/src" -name "__pycache__" -type d -prune -exec rm -rf {} +
cp -R "$root/data/knowledge" "$here/data/knowledge"
cp "$database" "$here/data/generated/contoso_aero.sqlite3"
sqlite3 "$here/data/generated/contoso_aero.sqlite3" "DROP TABLE ground_truth; VACUUM;"
echo "Staged the package and $(du -sh "$here/data" | cut -f1) of data in $here"
