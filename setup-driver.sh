#!/bin/sh
# One-time setup (per clone) for the pm/lock.json merge driver.
# Run inside the hermes-agent checkout AFTER cloning/forking:
#   sh ~/hermes-monterey/setup-driver.sh
# The driver definition lives in .git/config (not committable); the
# .gitattributes pointer IS committed (repo root).
set -e
git rev-parse --show-toplevel >/dev/null 2>&1 || {
  echo "Run this inside the hermes-agent repo." >&2
  exit 1
}
git config merge.hermes-pmlock.name "Monterey port: keep darwin-x64 Node v20 pin"
git config merge.hermes-pmlock.driver "$HOME/hermes-monterey/merge-driver.sh %O %A %B"
git check-attr merge pm/lock.json
echo "Driver installed. Test: git merge / rebase across a lock.json change."
