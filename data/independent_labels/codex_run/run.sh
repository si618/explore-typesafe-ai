#!/bin/bash
# Run Codex on one chunk inside bubblewrap: only the chunk, the prompt and an isolated CODEX_HOME are visible.
# Expects next to this script: chunks/cNN.json (5 packet cases each, in packet order),
# home/auth.json + home/config.toml (copy codex-config.toml), and an out/ directory.
# Usage: ./run.sh c00
set -euo pipefail
S=$(dirname "$(readlink -f "$0")"); c=$1; W=$(mktemp -d); cp "$S/chunks/$c.json" "$W/"
BIN=$(readlink -f "$(command -v codex)")  # codex-cli 0.155.1, a static binary
H=$(mktemp -d); cp "$S/home/auth.json" "$S/home/config.toml" "$H/"
bwrap --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib /lib64 \
  --ro-bind /etc/resolv.conf /etc/resolv.conf --ro-bind /etc/ssl /etc/ssl --ro-bind /etc/ca-certificates /etc/ca-certificates \
  --ro-bind /etc/passwd /etc/passwd --ro-bind "$BIN" /opt/codex --bind "$H" /codexhome --bind "$W" /work \
  --dev /dev --proc /proc --tmpfs /tmp --unshare-all --share-net --die-with-parent --clearenv \
  --setenv HOME /work --setenv CODEX_HOME /codexhome --setenv PATH /usr/bin --chdir /work \
  /opt/codex exec --strict-config --skip-git-repo-check --ephemeral --sandbox read-only \
    --disable browser_use --disable browser_use_external --disable computer_use --disable apps \
    --json -o /work/answer.json "$(cat "$S/prompt.txt")" < "$W/$c.json" > "$S/out/$c.events.jsonl" 2> "$S/out/$c.stderr"
cp "$W/answer.json" "$S/out/$c.answer.json"; ls -R "$W" > "$S/out/$c.workdir.txt"; rm -rf "$W" "$H"
