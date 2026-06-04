#!/usr/bin/env bash
# scripts/set-kali-mirrors.sh
# Small helper to choose the fastest official Kali mirrors and write them to /etc/apt/sources.list
# Usage:
#   ./scripts/set-kali-mirrors.sh           # dry-run (shows best mirrors)
#   sudo ./scripts/set-kali-mirrors.sh --apply   # actually replace /etc/apt/sources.list
#
set -euo pipefail

MIRRORLIST_URL="https://http.kali.org/README.mirrorlist"
TEST_PATH="/kali/dists/kali-rolling/InRelease"
DEFAULT_COUNT=3
TIMEOUT=3
TMPDIR="$(mktemp -d)"
DRY_RUN=1
COUNT=$DEFAULT_COUNT
CURL_OPTS="--max-time $TIMEOUT -sS -I"

usage() {
  cat <<EOF
set-kali-mirrors.sh — pick fastest Kali mirrors

Options:
  --apply        Replace /etc/apt/sources.list (requires root)
  --count N      Number of mirrors to select (default: $DEFAULT_COUNT)
  --help         Show this message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --count) COUNT="${2:-$COUNT}"; shift 2 ;;
    --help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

echo "[*] Downloading mirror list..."
if ! curl -fsS "$MIRRORLIST_URL" -o "$TMPDIR/mirrors.txt"; then
  echo "[!] Could not download mirror list from $MIRRORLIST_URL" >&2
  exit 1
fi

mapfile -t ALL_MIRRORS < <(grep -Eo 'https?://[^ ]+' "$TMPDIR/mirrors.txt" | sort -u)
if [[ ${#ALL_MIRRORS[@]} -eq 0 ]]; then
  echo "[!] No mirrors found in the mirrorlist" >&2
  exit 1
fi

echo "[*] Testing up to ${#ALL_MIRRORS[@]} mirrors (timeout ${TIMEOUT}s each)..."
# Test mirrors in parallel, record latency
latencies_file="$TMPDIR/latencies.txt"
: > "$latencies_file"

for m in "${ALL_MIRRORS[@]}"; do
  (
    url="${m%/}${TEST_PATH}"
    start=$(date +%s%3N)
    if curl $CURL_OPTS "$url" >/dev/null 2>&1; then
      end=$(date +%s%3N)
      latency=$((end - start))
      printf '%s %s\n' "$latency" "$m" >>"$latencies_file"
    fi
  ) &
done
wait

if [[ ! -s "$latencies_file" ]]; then
  echo "[!] No reachable mirrors responded successfully." >&2
  rm -rf "$TMPDIR"
  exit 1
fi

# sort by latency and pick top N
mapfile -t TOP < <(sort -n "$latencies_file" | awk '{print $2}' | uniq | head -n "$COUNT")

echo "[*] Top $COUNT mirrors (fastest first):"
for m in "${TOP[@]}"; do
  echo "  - $m"
done

if [[ $DRY_RUN -eq 1 ]]; then
  echo
  echo "[DRY-RUN] To apply these mirrors to /etc/apt/sources.list run:"
  echo "  sudo $0 --apply --count $COUNT"
  rm -rf "$TMPDIR"
  exit 0
fi

# Applying changes (requires root)
if [[ $EUID -ne 0 ]]; then
  echo "[!] Must be run as root to apply changes (use sudo)." >&2
  rm -rf "$TMPDIR"
  exit 1
fi

BACKUP="/etc/apt/sources.list.velox_backup.$(date -u +%Y%m%d_%H%M%S)"
echo "[*] Backing up /etc/apt/sources.list -> $BACKUP"
cp -a /etc/apt/sources.list "$BACKUP" || true

echo "[*] Writing new /etc/apt/sources.list with $COUNT mirrors"
{
  for m in "${TOP[@]}"; do
    printf 'deb %s kali-rolling main non-free contrib\n' "${m%/}"
  done
} > /etc/apt/sources.list

echo "[✓] Updated /etc/apt/sources.list (backup: $BACKUP)"
echo "[*] You may now run: apt update"
rm -rf "$TMPDIR"
exit 0
