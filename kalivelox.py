#!/usr/bin/env python3
# Kali-Velox - Aggressive mirror selector & system optimizer for Kali Rolling (2026 Edition)

"""
Kali-Velox
Auto-discovers the fastest Kali mirrors, optimizes DNS, enables HTTPS apt transport,
and performs a full system dist-upgrade. Intended for Kali Rolling (2026).

NOTES & SAFETY
- This script modifies /etc/apt/sources.list and /etc/resolv.conf and runs apt dist-upgrade.
- Run only on Kali Rolling systems and review the code before running in production.
- Backup of sources.list is saved to /etc/apt/sources.list.velox_backup.
"""

import subprocess
import sys
import os
import time
import concurrent.futures

try:
    import requests
    from colorama import Fore, Style, init
except Exception:
    print("[!] Missing Python dependencies. Run: sudo pip3 install -r /usr/local/lib/kalivelox/requirements.txt or see install.sh")
    sys.exit(2)

init(autoreset=True)

MIRROR_LIST = "https://http.kali.org/README.mirrorlist"
TEST_PATH = "/kali/dists/kali-rolling/InRelease"
TIMEOUT = 4
FASTEST = 3
MAX_WORKERS = 30


def banner():
    print(Fore.MAGENTA + Style.BRIGHT + r"""
⚡ Kali-Velox ⚡
[ 2026 | Speed | Precision ]
""")


def get_mirrors():
    try:
        r = requests.get(MIRROR_LIST, timeout=10)
        r.raise_for_status()
        return [l.strip() for l in r.text.splitlines() if l.strip().startswith(("http://","https://"))]
    except Exception as e:
        print(Fore.RED + f"[!] Could not download mirror list: {e}")
        return []


def test(m):
    url = m.rstrip('/') + TEST_PATH
    try:
        start = time.time()
        r = requests.head(url, timeout=TIMEOUT)
        latency_ms = (time.time()-start) * 1000
        return (m, latency_ms, r.status_code == 200)
    except Exception:
        return (m, float('inf'), False)


def safe_write_sources(mirrors):
    backup = '/etc/apt/sources.list.velox_backup'
    try:
        subprocess.run(["cp", "/etc/apt/sources.list", backup], check=False)
    except Exception:
        pass
    try:
        with open('/etc/apt/sources.list', 'w') as f:
            for m in mirrors:
                f.write(f"deb {m} kali-rolling main non-free contrib\n")
        print(Fore.CYAN + f"[*] Wrote {len(mirrors)} mirror entries to /etc/apt/sources.list (backup: {backup})")
    except Exception as e:
        print(Fore.RED + f"[!] Failed to write sources.list: {e}")


def safe_write_resolv():
    # This will overwrite /etc/resolv.conf. On systems using systemd-resolved, users may wish to adapt.
    try:
        with open('/etc/resolv.conf', 'w') as f:
            f.write('nameserver 8.8.8.8\n')
            f.write('nameserver 1.1.1.1\n')
        print(Fore.CYAN + "[*] Wrote resolv.conf with Google & Cloudflare DNS")
        # Attempt to flush caches if systemd-resolve exists
        subprocess.run(["systemd-resolve", "--flush-caches"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception:
        print(Fore.YELLOW + "[!] Could not write/flush DNS settings. You may need to adjust your resolver manually.")


def apt_maintenance():
    try:
        subprocess.run(["apt", "install", "-y", "apt-transport-https"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["apt", "clean"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["apt", "update"], check=False)
        subprocess.run(["apt", "dist-upgrade", "-y"], check=False)
    except Exception as e:
        print(Fore.RED + f"[!] Apt operations encountered an issue: {e}")


def main():
    if os.geteuid() != 0:
        print(Fore.RED + "[!] Kali-Velox must be run as root. Use: sudo kalivelox or sudo python3 kalivelox.py")
        sys.exit(1)

    banner()
    mirrors = get_mirrors()
    if not mirrors:
        print(Fore.RED + "[!] No mirrors found. Exiting.")
        sys.exit(1)

    print(Fore.YELLOW + f"[*] Testing {len(mirrors)} mirrors (this may take a few seconds)...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(mirrors))) as ex:
        for res in ex.map(test, mirrors):
            if res[2]:
                results.append((res[0], res[1]))

    if not results:
        print(Fore.RED + "[!] No reachable mirrors responded successfully. Exiting.")
        sys.exit(1)

    results.sort(key=lambda x: x[1])
    fastest = [r[0] for r in results[:FASTEST]]
    print(Fore.GREEN + "[✓] Fastest mirrors:")
    for f in fastest:
        print("    - ", f)

    safe_write_sources(fastest)
    safe_write_resolv()
    apt_maintenance()

    print(Fore.GREEN + "[✓] Kali-Velox complete. System optimization steps have finished.")


if __name__ == '__main__':
    main()
