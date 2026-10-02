#!/usr/bin/env bash
# Report which tools the ihmtools plugin can use on this machine.
# Installs nothing and always exits 0. One "name  status" line per tool.
set -u

row() { printf '%-12s %s\n' "$1" "$2"; }

py=$(command -v python3 || command -v python || true)
if [ -n "$py" ]; then
  row python "$py ($("$py" -c 'import sys; print(sys.version.split()[0])'))"
  for dist in ihm msgpack gemmi; do
    ver=$("$py" -c "import importlib.metadata as m; print(m.version('$dist'))" 2>/dev/null)
    row "$dist" "${ver:-missing (install: pip install $dist)}"
  done
else
  row python "missing (install Python 3.9 or newer)"
fi

for tool in ihmv ihmdep; do
  row "$tool" "$(command -v "$tool" || echo 'missing (install: pip install ihmtools)')"
done
row uv "$(command -v uv || echo 'missing (optional: https://docs.astral.sh/uv/)')"
row apptainer "$(command -v apptainer || command -v singularity || echo 'missing (optional: local IHMValidation only)')"

chimerax=$(command -v chimerax || command -v ChimeraX || true)
if [ -z "$chimerax" ]; then
  for app in /Applications/ChimeraX*.app/Contents/bin/ChimeraX; do
    [ -x "$app" ] && chimerax=$app
  done
fi
row chimerax "${chimerax:-missing (optional: geometry checks and images)}"

if [ -z "${IHMV_SIF:-}" ]; then
  row IHMV_SIF "unset (optional: path to a local IHMValidation image)"
elif [ -f "$IHMV_SIF" ]; then
  row IHMV_SIF "$IHMV_SIF"
else
  row IHMV_SIF "set to $IHMV_SIF but no such file"
fi
exit 0
