# ⚡ Kali-Velox – Production-grade Kali Linux Optimizer (2026)

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Kali Rolling](https://img.shields.io/badge/Kali-Rolling-blue)](https://www.kali.org/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green)](https://python.org)
[![Tests](https://github.com/joyelkhan/Kali-Velox/actions/workflows/test.yml/badge.svg)](.github/workflows/test.yml)

**Auto‑selects verified fastest mirrors, persistent DNS, parallel APT, RAM cache, automatic rollback – one command.**

---

## 🚀 What's New in 2026.06

| Feature | Description |
|---------|-------------|
| ✅ GPG verification | Rejects mirrors without valid Kali signature |
| ✅ Persistent DNS | Uses systemd-resolved or nmcli – survives reboot |
| ✅ Automatic rollback | Restores original sources if upgrade fails |
| ✅ Parallel APT | 15 pipeline depth, queue mode host |
| ✅ RAM cache | APT lists stored in tmpfs (200MB) |
| ✅ IPv6 preference | Automatically uses IPv6 when available |
| ✅ Bandwidth limiting | `--limit 10` to cap at 10 Mbps |
| ✅ Dry-run mode | `--dry-run` to simulate without changes |
| ✅ Systemd timer | Weekly automatic optimization |
| ✅ Version flag | `--version` for CI/CD integration |

---

## 📦 Installation

```bash
git clone https://github.com/joyelkhan/Kali-Velox.git
cd Kali-Velox
chmod +x install.sh
sudo ./install.sh
