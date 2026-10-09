#!/bin/sh
# Merge driver for pm/lock.json (Hermes Monterey port).
# Invoked by git as: merge-driver.sh %O %A %B
# Takes the NEWER upstream side, re-applies the darwin-x64 Node v20 pin,
# writes the merged result to %A. All other upstream tool updates are kept.
# If the lock schema ever changes incompatibly, python exits nonzero and
# git falls back to a manual conflict (fail-closed).
O="$1" A="$2" B="$3"
GITDIR=$(git rev-parse --git-dir 2>/dev/null)
# Rebase/cherry-pick: ours (%A) is the new upstream base. Plain merge: ours
# is your branch, upstream is theirs (%B).
if [ -d "$GITDIR/rebase-merge" ] || [ -d "$GITDIR/rebase-apply" ]; then
  SRC="$A"
else
  SRC="$B"
fi
python3 - "$SRC" "$A" <<'EOF'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
d["packages"]["node"]["artifacts"]["darwin-x64"] = {
    "sha256": "d0f34126b41532719035fdb3484d5c4210f18cd2489d6098dcc57802dfb80a71",
    "url": "https://nodejs.org/dist/v20.19.0/node-v20.19.0-darwin-x64.tar.xz",
}
open(dst, "w").write(json.dumps(d, indent=2) + "\n")
EOF
