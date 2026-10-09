#!/usr/bin/env python3
"""Hermes Monterey (Intel) port — idempotent re-pinner.

Re-applies the 5 port patches by KEY, not by diff, so upstream version bumps
(e.g. Node 26.7.0 -> 26.8.0 in pm/lock.json) never cause merge conflicts:
  1. pm/update.py ............ cap Node lookup at major <= 20
  2. pm/lock.json ............. pin ONLY darwin-x64 Node to v20.19.0 (+sha256)
  3. package.json .............. allow ^20.19.0 in engines.node
  4. package-lock.json ......... same, root packages[""] entry only
  5. scripts/build/node-deps.mjs  drop hardcoded --engine-strict (repo .npmrc
                                 forces strict; the CLI flag would beat the
                                 npm_config_engine_strict=false escape hatch)

Usage:
  repin.py           apply all patches (safe to re-run)
  repin.py --check   exit 0 if all applied, 1 otherwise (no writes)

After running, re-sync tools:
  <tools-python> -m pm.cli install --without agent-browser --without cua-driver
(see reinstall.sh). Requires the ~/.zshrc toolchain env from the README.
"""
import json
import sys
from pathlib import Path

REPO = Path.home() / ".hermes" / "hermes-agent"
NODE20_URL = "https://nodejs.org/dist/v20.19.0/node-v20.19.0-darwin-x64.tar.xz"
NODE20_SHA = "d0f34126b41532719035fdb3484d5c4210f18cd2489d6098dcc57802dfb80a71"
ENGINE_PREFIX = "^20.19.0 || "

UPDATE_SNIPPET = '''            # LOCAL PATCH for macOS 12 Monterey: Node 22+ links a newer
            # libc++ (__libcpp_verbose_abort) than Monterey ships, so the
            # staged binary fails verification. Cap at the Node 20.x line.
            if int(v.split(".")[0]) > 20:
                continue
'''
UPDATE_ANCHOR = "        if re.fullmatch(r\"\\d+\\.\\d+\\.\\d+\", v):\n"

MJS_OLD = "  const args = ['ci', '--no-audit', '--no-fund', '--engine-strict', '--include=dev',"
MJS_NEW = """  // Monterey port: engines are relaxed for Node 20 in package.json, but the
  // repo .npmrc forces engine-strict and this hardcoded flag would beat the
  // npm_config_engine_strict=false escape hatch (CLI beats env). Install
  // without the strict flag so engines stay advisory on this host.
  const args = ['ci', '--no-audit', '--no-fund', '--include=dev',"""

results = []


def note(ok, label, detail=""):
    results.append(ok)
    print(("OK   " if ok else "MISS ") + label + ((" — " + detail) if detail else ""))


def patch_update_py(check):
    p = REPO / "pm" / "update.py"
    t = p.read_text()
    if "Cap at the Node 20.x line" in t:
        note(True, "pm/update.py (already capped)")
        return
    if UPDATE_ANCHOR not in t:
        note(False, "pm/update.py (anchor not found — inspect manually)")
        return
    if check:
        note(False, "pm/update.py")
        return
    p.write_text(t.replace(UPDATE_ANCHOR, UPDATE_ANCHOR + UPDATE_SNIPPET, 1))
    note(True, "pm/update.py (capped)")


def patch_pm_lock(check):
    p = REPO / "pm" / "lock.json"
    lock = json.loads(p.read_text())
    cur = lock["packages"]["node"]["artifacts"]["darwin-x64"]
    if cur.get("url") == NODE20_URL and cur.get("sha256") == NODE20_SHA:
        note(True, "pm/lock.json darwin-x64 (already v20.19.0)")
        return
    if check:
        note(False, "pm/lock.json darwin-x64", "currently " + cur.get("url", "?").rsplit("/", 1)[-1])
        return
    lock["packages"]["node"]["artifacts"]["darwin-x64"] = {
        "sha256": NODE20_SHA,
        "url": NODE20_URL,
    }
    # Preserve the file's existing formatting (2-space indent + trailing \n).
    p.write_text(json.dumps(lock, indent=2) + "\n")
    note(True, "pm/lock.json darwin-x64 (pinned v20.19.0)")


def patch_engines(path, entry, check, label):
    """Prepend ^20.19.0 to an engines.node range unless a 20.x alternative exists."""
    raw = Path(path).read_text()
    data = json.loads(raw)
    node = data
    for key in entry:
        node = node[key]
    rng = node["engines"]["node"]
    import re
    if re.search(r"(?:^|[\s|])\^?20\.", rng):
        note(True, label + " (already allows 20.x)")
        return
    if check:
        note(False, label, "currently " + rng[:40])
        return
    node["engines"]["node"] = ENGINE_PREFIX + rng
    indent = 2
    Path(path).write_text(json.dumps(data, indent=indent) + ("\n" if raw.endswith("\n") else ""))
    note(True, label + " (20.x allowed)")


def patch_mjs(check):
    p = REPO / "scripts" / "build" / "node-deps.mjs"
    t = p.read_text()
    if "--engine-strict" not in t and "Monterey port" in t:
        note(True, "node-deps.mjs (flag already dropped)")
        return
    if MJS_OLD not in t:
        note(False, "node-deps.mjs (pattern not found — inspect manually)")
        return
    if check:
        note(False, "node-deps.mjs")
        return
    p.write_text(t.replace(MJS_OLD, MJS_NEW, 1))
    note(True, "node-deps.mjs (flag dropped)")


def main():
    global REPO
    check = "--check" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            REPO = Path(arg)  # test hook: run against a copy of the tree
    if not (REPO / "pm" / "lock.json").exists():
        print("Repo not found at " + str(REPO))
        return 2
    patch_update_py(check)
    patch_pm_lock(check)
    patch_engines(REPO / "package.json", [], check, "package.json engines")
    patch_engines(REPO / "package-lock.json", ["packages", ""], check, "package-lock.json engines")
    patch_mjs(check)
    print(("ALL APPLIED" if all(results) else "INCOMPLETE") + " (%d/%d)" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
