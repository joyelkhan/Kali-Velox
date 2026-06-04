#!/bin/bash
set -e
echo "[*] Installing Kali-Velox dependencies..."
apt update
apt install -y python3 python3-pip python3-requests python3-colorama
pip3 install --upgrade requests colorama

cp kalivelox.py /usr/local/bin/kalivelox
chmod +x /usr/local/bin/kalivelox

echo "[✓] Installed. Commands:"
echo "    sudo kalivelox              # Run once"
echo "    sudo kalivelox --install-timer  # Run weekly automatically"
echo "    kalivelox --version         # Show version"
