#!/bin/sh
# Hermes Monterey (Intel) port — full rebuild from the current tree.
# No sudo. Everything lives in $HOME. Idempotent: safe to re-run.
set -e
export PATH="$HOME/.cargo/bin:$HOME/.local/node20/bin:$HOME/.local/openssl/bin:$PATH"
export OPENSSL_DIR="$HOME/.local/openssl"
export PKG_CONFIG_PATH="$HOME/.local/openssl/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export npm_config_cache="$HOME/.npm-user"
export npm_config_engine_strict=false

H="$HOME/.hermes/hermes-agent"
[ -d "$H" ] || { echo "No checkout at $H" >&2; exit 1; }
cd "$H"

echo "==> 1/3 repin (key-based patches)"
python3 "$HOME/hermes-monterey/repin.py" || {
  echo "repin incomplete — inspect output above" >&2; exit 1
}

echo "==> 2/3 pm install (tools + Python venv)"
BOOT_PY=$(ls -d "$HOME"/.hermes/tools/python-*/bin/python3 2>/dev/null | head -1)
if [ ! -x "$BOOT_PY" ]; then
  echo "No tools Python found. Install Xcode CLT, then fetch uv + python:" >&2
  echo "  curl -fsSL https://github.com/astral-sh/uv/releases/download/0.12.3/uv-x86_64-apple-darwin.tar.gz -o /tmp/uv.tgz" >&2
  echo "  mkdir -p /tmp/uvboot && tar -xzf /tmp/uv.tgz -C /tmp/uvboot" >&2
  echo "  /tmp/uvboot/uv-x86_64-apple-darwin/uv python install 3.14" >&2
  exit 1
fi
"$BOOT_PY" -m pm.cli install --without agent-browser --without cua-driver

echo "==> 3/3 TUI/web JS deps (official flow)"
"$(find "$HOME/.hermes/tools" -maxdepth 3 -path "*bin/node" | head -1)" \
  scripts/build/node-deps.mjs --source "$H" --reuse \
  --workspace ui-tui --workspace web

echo "==> done. Next: source ~/.zshrc && hermes doctor"
