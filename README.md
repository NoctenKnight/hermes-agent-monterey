# Hermes Agent on macOS 12 Monterey (Intel) — port kit

Hermes Agent upstream requires **macOS 14+** (Desktop is Apple-Silicon-only).
This kit records how it was made to work on an **Intel Mac running macOS 12.7.6**,
and how to keep it working across updates. Nothing here needs `sudo`;
everything lives in `$HOME`.

Machine this was built on: Monterey 12.7.6, x86_64, 32 GB RAM,
AMD Radeon R9 M380 2 GB (unusable for inference — CPU-only),
Xcode CLT 14 (clang 14, `xcode-select -p` → `/Library/Developer/CommandLineTools`),
system Python 3.9.6 (too old — the installer brings its own).

## Version inventory (verified working)

| Piece | Version | Why this one |
|---|---|---|
| Ollama | 0.34.0 (`Ollama-darwin.zip`, GitHub release) | 0.40.x needs macOS 14+; 0.34 is the newest that serves on Monterey |
| Ollama models | `tinyllama` 637 MB · `nous-hermes` 3.8 GB · `llama3.1:8b` 4.9 GB | Hermes hard-requires ≥64K context → `llama3.1` (128K native) with `OLLAMA_CONTEXT_LENGTH=65536` |
| Hermes Agent | v0.21.6+302 (`main`, Intel checkout) | — |
| Node for Hermes | **v20.19.0** (darwin-x64) + npm 10.8.2 | Last line that runs on Monterey; v22+ needs macOS 13.5+ `libc++` (`__libcpp_verbose_abort`) |
| Python for Hermes | 3.14.7 (astral standalone, via pm) | pm itself requires `>=3.14,<3.15` |
| Rust | **1.99.0** via rustup (`~/.cargo`) | Builds `cryptography` 50.0.1 from source (no cp314/Intel wheel on PyPI — only `macosx_11_0_arm64`) |
| OpenSSL | **3.5.4**, built from source to `~/.local/openssl` (`./Configure --prefix=$HOME/.local/openssl no-tests && make && make install`) | The `cryptography` Rust build fails with “Could not find directory of OpenSSL installation” without it |
| uv | 0.12.3 | Pinned by the Hermes installer |

## What was done (record, in order)

1. **Ollama downgrade.** Deleted v0.40.1 (`/Applications/Ollama.app`), installed v0.34.0
   as `/Applications/Ollama.app` so the existing `/usr/local/bin/ollama` symlink
   follows it. Verified `ollama --version` → 0.34.0, `serve` up, pulled
   `tinyllama` (success) and ran it.
2. **Hermes install (official script).** `install.sh --non-interactive --skip-browser
   --skip-computer-use`. Got through git/uv/Python 3.14/ffmpeg/ripgrep, then died on
   Node 22+ (`dyld: Symbol not found`). Browser/computer-use skipped (Chromium/CUA
   won't run here); Desktop skipped (Apple-Silicon-only upstream).
3. **Patch 1 — `pm/update.py`:** cap `node_latest_versions()` at major ≤ 20.
4. **Patch 2 — `pm/lock.json`:** pin ONLY `darwin-x64` Node to v20.19.0 (+sha256);
   all 8 other targets stay at upstream v26. (Lock edits must preserve the file's
   2-space indent + trailing newline, or the diff explodes — learned the hard way.)
5. **Rust + OpenSSL** (table above), exported via `~/.zshrc` (step 1 below).
6. **Context fix.** Hermes rejects models under 64K context (`nous-hermes` = 4K).
   Serve with `OLLAMA_CONTEXT_LENGTH=65536`, use `llama3.1:8b` (KV cache ≈ 8.6 GB +
   4.9 GB weights ≈ 14 GB loaded — fits 32 GB RAM). First chat answered correctly
   (`OLLAMA_OK`, 8m42s on CPU — slow but proven).
7. **OpenRouter (optional, fast).** Key → `~/.hermes/.env` as `OPENROUTER_API_KEY`
   (600 perms), provider `openrouter`, free model with ≥64K + tools
   (`nvidia/nemotron-3-super-120b-a12b:free` worked in 8s; `google/gemma-4-31b-it:free`
   429'd at the time). Remember to `hermes config unset model.base_url` when leaving
   the local endpoint, or requests still go to localhost (Hermes warns you itself).
8. **TUI.** `scripts/build/node-deps.mjs` gates on `engines` (Node ^22…) twice —
   patched root `package.json` + root `package-lock.json` `packages[""]` entry to
   allow `^20.19.0`, dropped the hardcoded `--engine-strict` (it beats the
   `npm_config_engine_strict=false` escape hatch; repo `.npmrc` forces strict).
   Also required: `npm_config_cache=$HOME/.npm-user` (system `~/.npm` is
   root-owned from an old sudo run → EACCES). Official flow then exits 0
   (555 packages, receipt written); `hermes --tui` launches in a real terminal
   (no TTY in headless shells — expected).
9. **Tests:** clean-slate rebuild exit 0 · CLI loop PASS (local + cloud) ·
   TUI dep-build PASS, TUI render needs a real terminal · file-write tool PASS
   (`~/Desktop/monterey.txt` = `Hello World`) · arch sanity PASS (Intel-only,
   no hardcoded home paths).

## Fresh install on another Monterey Intel Mac (easy path)

Prerequisites: Xcode CLT (`xcode-select --install`), git, curl, ~30 GB free.

```bash
# 0. Get this kit:
git clone https://github.com/NoctenKnight/hermes-agent-monterey.git ~/hermes-monterey

# 1. Toolchain env (persist it):
cat >> ~/.zshrc <<'EOF'
export PATH="$HOME/.cargo/bin:$HOME/.local/node20/bin:$HOME/.local/openssl/bin:$PATH"
export OPENSSL_DIR="$HOME/.local/openssl"
export PKG_CONFIG_PATH="$HOME/.local/openssl/lib/pkgconfig:$PKG_CONFIG_PATH"
export PATH="$HOME/.local/bin:$PATH"
export npm_config_cache="$HOME/.npm-user"
export npm_config_engine_strict=false
EOF
source ~/.zshrc

# 2. Rust + Node 20 + OpenSSL 3.5.4 (see table; ~15 min, no sudo):
#    rustup:  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
#    node20:  unpack nodejs.org/dist/v20.19.0/node-v20.19.0-darwin-x64.tar.gz to ~/.local/node20
#    openssl: Configure --prefix=$HOME/.local/openssl no-tests && make && make install

# 3. Ollama 0.34 + a 64K model:
#    install Ollama-darwin.zip v0.34.0 as /Applications/Ollama.app
#    OLLAMA_CONTEXT_LENGTH=65536 ollama serve  (keep running; GUI app lacks the setting)
#    ollama pull llama3.1

# 4. Hermes + this kit's patches (plain sh: zsh has no process substitution):
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh
bash /tmp/hermes-install.sh \
  --non-interactive --skip-browser --skip-computer-use   # fails at Node: expected
python3 ~/hermes-monterey/repin.py                        # apply the 5 patches
sh ~/hermes-monterey/reinstall.sh                         # tools + venv + JS deps

# 5. Point Hermes at Ollama:
hermes config set model.default "llama3.1:latest"
hermes config set model.provider custom
hermes config set model.base_url "http://127.0.0.1:11434/v1"
hermes config set custom_providers \
  '[{"name":"ollama","base_url":"http://127.0.0.1:11434/v1","model":"llama3.1:latest","provider_key":"ollama"}]'
hermes doctor && hermes chat -q "Reply with exactly: OLLAMA_OK"
```

## Reapplying after `hermes update` (no conflicts, ever)

Core Hermes never self-updates (the 24 h check is plugins-only and apply needs
opt-in), so this is only for manual updates. The installer stashes local changes
(`hermes-install-autostash-*`) — don't fight it:

```bash
cd ~/.hermes/hermes-agent
hermes update                                   # or re-run install.sh
git checkout origin/main -- pm/lock.json package.json package-lock.json \
  pm/update.py scripts/build/node-deps.mjs .gitattributes  # accept upstream…
python3 ~/hermes-monterey/repin.py              # …re-pin by key (immune to version bumps)
sh ~/hermes-monterey/reinstall.sh               # re-sync tools
```

Why not `merge=ours` in `.gitattributes`? It would freeze the ENTIRE lockfile and
silently drop every upstream dependency/security update — and once the frozen
`package-lock.json` drifts from `package.json`, `npm ci` hard-fails. Worse than
the 30-second conflict it avoids. (It also needs a per-clone
`git config merge.ours.driver true` to work at all.)

Automatic help already wired:
- `pm/lock.json` has a real merge driver (`merge=hermes-pmlock`, see
  `.gitattributes` in the repo + `setup-driver.sh` + `merge-driver.sh` here):
  on rebase/merge it keeps ALL upstream updates and re-pins only the darwin-x64
  Node entry. Run `sh ~/hermes-monterey/setup-driver.sh` once per clone.
- `git rerere` is enabled — any classic conflict you resolve once is remembered.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `dyld: Symbol not found (__libcpp_verbose_abort)` for `node` | Node 22+ on macOS 12 | Repin to Node v20.19.0 (`repin.py`); never newer on Monterey |
| `✗ node: staged entry failed verification` during install | Same as above (pm probing the binary) | Same fix |
| `Error: node 20.19.0 violates ^22…` from `node-deps.mjs` / TUI won't start | Root `engines` gate | `repin.py` relaxes root `package.json` + `package-lock.json`; needs `npm_config_engine_strict=false` too (repo `.npmrc` forces strict; CLI flag in script beats env, hence the `.mjs` patch) |
| `npm error code EACCES` / weird exit -13, 243 | `~/.npm` owned by root (old sudo run) | `npm_config_cache=$HOME/.npm-user` (in `.zshrc`); don't `chown` without need |
| `cryptography` build: “Could not find directory of OpenSSL installation” | No system OpenSSL dev files on macOS | Build OpenSSL 3.5.4 to `~/.local`, export `OPENSSL_DIR` + `PKG_CONFIG_PATH` (persisted in `.zshrc`) |
| `cryptography` still fails to link | Missing Rust or stale env in current shell | Install rustup stable, `source ~/.zshrc`, re-run `reinstall.sh` |
| `context window 4,096 below minimum 64,000` | Small-context local model | `OLLAMA_CONTEXT_LENGTH=65536 ollama serve` + 64K-native model (`llama3.1:8b`); 7B-class non-GQA models can't do 64K in 32 GB RAM — prefer GQA models (Qwen/Llama-3) |
| `HTTP 429` on OpenRouter free model | Per-model free-tier rate limits (key itself was valid) | Wait a minute or switch free model (`nemotron-3-super-120b-a12b:free` worked); `hermes fallback add` for a backup |
| Requests still hit localhost after switching provider | Stale `model.base_url` outranks provider | `hermes config unset model.base_url` (Hermes warns about this itself) |
| `hermes: command not found` | `~/.local/bin` not on PATH (installer skips rc edit non-interactively) | The `case ":$PATH:"…` line in `.zshrc` above; open a new terminal |
| `install.sh` says “local changes stashed” | Installer autostash (by design) | Finish the install, then `repin.py` + `reinstall.sh`; or commit to your branch and rebase |
| TUI exits instantly / blank in headless shell | Ink needs a real TTY | Run `hermes --tui` in a normal terminal; not a port bug |
| `git diff` on `pm/lock.json` explodes to 1300 lines | `json.dump` with wrong indent | File uses 2-space indent + trailing `\n` — `repin.py` preserves both |
| First chat takes ~9 min, then faster | 8B model on CPU + ~11K-token agent system prompt | Expected on Intel; keep model loaded, or use a cloud model for interactive work |
| GPU questions | Ollama x86 is CPU-only upstream; 2 GB VRAM couldn't hold the model anyway; old Metal family | No GPU path on this machine — CPU or cloud |

## Known limitations

- No Apple-Silicon-only pieces: Desktop app, computer-use driver, browser automation (Chromium) are skipped.
- `~/.hermes/tools/node-26.7.0-darwin-x64/` is *named* 26.7.0 (from the lock's version
  field) but *contains* v20.19.0 — cosmetic, from pm's directory naming. Don't “fix”
  the dirname; pm manages it.
- `hermes update` / re-running `install.sh` wipes repo patches (autostash) — use the
  reapply flow above, never `git stash pop` blindly onto a moved main.
- API keys live in `~/.hermes/.env` (600), outside the repo — safe to commit the
  6 patched files; never commit `.env`.
- Upstream may one day require Node 22+ *APIs* (not just the version gate) or
  Python 3.15-only syntax — then this port needs real code work, not pins.

## Files in this kit
- `README.md` — this file
- `LICENSE` — MIT (port © 2026 nocten; upstream excerpts © 2025 Nous Research)
- `repin.py` — idempotent, key-based patch applier (`--check` for verify-only)
- `reinstall.sh` — repin + pm tools + JS deps + doctor hint (one shot)
- `merge-driver.sh` / `setup-driver.sh` — auto-keep the Node pin across rebases
- `monterey-intel-port.diff` — frozen record of the original 5-file patch

## Contact

Port maintained by **nocten** — contact@kartikchandra.com.
Upstream project: Nous Research, https://github.com/NousResearch/hermes-agent (MIT).

## License

This kit is MIT licensed (see `LICENSE`). It complies with the upstream MIT
license: the upstream `LICENSE` file in the fork is untouched, the Nous
Research copyright notice is retained, and this port's modifications are
identified in the commit history. `monterey-intel-port.diff` contains upstream
code excerpts — still © 2025 Nous Research, MIT.
