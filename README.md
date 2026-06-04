# ⚡ Kali-Velox – 2026 Edition

Kali-Velox is a lightweight, focused utility that auto-discovers the fastest Kali Linux mirrors, optimizes DNS settings, enables HTTPS apt transport, and performs a full dist-upgrade — all in one command.

Badges
- License: MIT
- Target: Kali Rolling
- Language: Python 3.11+

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Kali Rolling](https://img.shields.io/badge/Kali-Rolling-blue)](https://www.kali.org/) [![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green)](https://python.org)

---

Why Kali-Velox?
- Quick mirror discovery: Parallel-tests mirrors listed by Kali and picks the fastest responders.
- One-shot system optimization: Rewrites your /etc/apt/sources.list to use the fastest mirrors, switches resolvers to low-latency public DNS, ensures apt-transport-https is present, and runs apt update & dist-upgrade.
- Minimal footprint: Single Python script with two small runtime dependencies (requests, colorama) and a simple installer.

Important safety note
- This script modifies system files and runs a distribution upgrade. Review the code before running and ensure you have backups.
- Use --dry-run to preview changes without making them. Default actions are aggressive: changing sources.list, DNS, and running upgrades.

Repository structure
Kali-Velox/
├── kalivelox.py          # Main script
├── README.md             # Documentation (this file)
├── LICENSE               # MIT License
├── requirements.txt      # Python dependencies
├── install.sh            # One-click installer
└── .github/
    └── FUNDING.yml       # Optional sponsorship

Quick install
1. Clone the repository:
   git clone https://github.com/joyelkhan/Kali-Velox.git
   cd Kali-Velox

2. Make installer executable and run:
   chmod +x install.sh
   sudo ./install.sh

3. Run Kali-Velox:
   sudo kalivelox

Or run directly (without installing):
   sudo python3 kalivelox.py

Usage details
- Command-line options (new):
  --dry-run       Show actions without making changes (strongly recommended for first runs)
  --no-dns        Do not change DNS settings
  --mirrors N     Number of fastest mirrors to write (default: 3)
  --max-workers N Number of concurrent tests (default: 30)
  --skip-upgrade  Do not run `apt dist-upgrade`
  --backup-dir    Directory to store backups (optional)

- What it does:
  1. Downloads official mirror list from https://http.kali.org/README.mirrorlist
  2. Performs parallel HEAD checks to measure latency to /kali/dists/kali-rolling/InRelease
  3. Selects the top N responders and writes them to /etc/apt/sources.list (backup saved at /etc/apt/sources.list.velox_backup.TIMESTAMP)
  4. If systemd-resolved manages DNS, writes a drop-in file in /etc/systemd/resolved.conf.d/ to set DNS; otherwise overwrites /etc/resolv.conf
  5. Flushes resolver caches if possible
  6. Ensures apt-transport-https is installed
  7. Runs apt update and apt dist-upgrade -y (unless --skip-upgrade)

- Customization / common changes:
  - Use --dry-run to preview actions without making system changes.
  - Use --no-dns to prevent DNS modification.
  - Adjust --mirrors and --max-workers to control selection behavior.

Contributing
- Bug reports and pull requests welcome. Keep changes focused on performance, safety, and maintainability.

License
This project is licensed under the MIT License. See LICENSE for details.

Acknowledgements
- Velox: Latin for "swift" — chosen to convey speed and precision.
- Built for Kali 2026 rolling users who want a faster apt experience.
