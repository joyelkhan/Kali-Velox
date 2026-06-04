#!/usr/bin/env bash
# Kali-Velox installer (2026)
set -euo pipefail

echo "[*] Updating package lists..."
apt update

echo "[*] Installing runtime prerequisites..."
apt install -y python3 python3-pip

# Install Python dependencies
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Install the script to /usr/local/bin
install -m 0755 kalivelox.py /usr/local/bin/kalivelox

cat <<'EOF'

[✓] Kali-Velox installed.
Run with: sudo kalivelox
If you prefer not to install, run in-place with: sudo python3 kalivelox.py
Tip: Use --dry-run the first time to preview changes.

EOF
