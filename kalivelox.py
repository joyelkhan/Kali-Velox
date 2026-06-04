#!/usr/bin/env python3
# Kali-Velox - Aggressive mirror selector & system optimizer for Kali Rolling (2026 Edition)
"""
Kali-Velox
Auto-discovers the fastest Kali mirrors, optimizes DNS settings, enables HTTPS apt transport,
and performs a full system dist-upgrade. Intended for Kali Rolling (2026).

SAFETY NOTES
- This script modifies /etc/apt/sources.list and may modify DNS configuration and run apt dist-upgrade.
- Review the code and run in --dry-run mode first. Prefer testing in a VM/container.
- Backups of modified files include timestamps.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import os
import subprocess
import sys
import time
from shutil import which

try:
    import requests
    from colorama import Fore, Style, init
except Exception:
    print("[!] Missing Python dependencies. Install with: sudo pip3 install -r requirements.txt or run: sudo ./install.sh")
    sys.exit(2)

init(autoreset=True)

MIRROR_LIST = "https://http.kali.org/README.mirrorlist"
TEST_PATH = "/kali/dists/kali-rolling/InRelease"
TIMEOUT = 4
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


def timestamp():
    return datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')


def backup_file(path: str, suffix: str = '') -> str:
    if not os.path.exists(path):
        return ''
    br = f"{path}.velox_backup{('.' + suffix) if suffix else ''}"
    try:
        subprocess.run(["cp", path, br], check=False)
        return br
    except Exception:
        return ''


def safe_write_sources(mirrors, dry_run=False, backup_dir=None):
    target = '/etc/apt/sources.list'
    bakname = f"/etc/apt/sources.list.velox_backup.{timestamp()}"
    if backup_dir:
        try:
            os.makedirs(backup_dir, exist_ok=True)
            bakname = os.path.join(backup_dir, os.path.basename(bakname))
        except Exception:
            pass

    print(Fore.CYAN + f"[*] Backing up {target} to {bakname}")
    if dry_run:
        print(Fore.YELLOW + "[DRY-RUN] Would write new sources.list with the following entries:")
        for m in mirrors:
            print("    ", f"deb {m} kali-rolling main non-free contrib")
        return bakname

    # Backup
    try:
        subprocess.run(["cp", target, bakname], check=False)
    except Exception:
        print(Fore.YELLOW + "[!] Could not create backup of sources.list")

    try:
        with open(target, 'w') as f:
            for m in mirrors:
                f.write(f"deb {m} kali-rolling main non-free contrib\n")
        print(Fore.CYAN + f"[*] Wrote {len(mirrors)} mirror entries to {target} (backup: {bakname})")
    except Exception as e:
        print(Fore.RED + f"[!] Failed to write sources.list: {e}")

    return bakname


def is_systemd_resolved_managed() -> bool:
    try:
        if os.path.islink('/etc/resolv.conf'):
            target = os.readlink('/etc/resolv.conf')
            if 'systemd' in target or '/run/systemd/resolve' in target:
                return True
    except Exception:
        pass
    return False


def write_systemd_resolved_conf(dns_list: list[str], dry_run=False):
    dropin_dir = '/etc/systemd/resolved.conf.d'
    dropin_file = os.path.join(dropin_dir, '90-kalivelox.conf')
    content = '[Resolve]\n' + f"DNS={' '.join(dns_list)}\n" + "FallbackDNS=1.1.1.1 8.8.4.4\n"
    print(Fore.CYAN + f"[*] Will write systemd-resolved drop-in: {dropin_file}")
    if dry_run:
        print(Fore.YELLOW + "[DRY-RUN] Would create file with:\n" + content)
        return dropin_file
    try:
        os.makedirs(dropin_dir, exist_ok=True)
        with open(dropin_file, 'w') as f:
            f.write(content)
        # Try to reload systemd-resolved
        if which('systemctl'):
            subprocess.run(['systemctl', 'reload-or-restart', 'systemd-resolved'], check=False)
        print(Fore.CYAN + f"[*] Wrote {dropin_file} and reloaded systemd-resolved")
    except Exception as e:
        print(Fore.RED + f"[!] Failed to write systemd resolved drop-in: {e}")
    return dropin_file


def write_resolv_conf(dns_list: list[str], dry_run=False):
    target = '/etc/resolv.conf'
    content = ''.join([f"nameserver {d}\n" for d in dns_list])
    print(Fore.CYAN + f"[*] Will write {target} with DNS {dns_list}")
    if dry_run:
        print(Fore.YELLOW + "[DRY-RUN] Would overwrite /etc/resolv.conf with:\n" + content)
        return target
    try:
        # Backup
        bak = f"{target}.velox_backup.{timestamp()}"
        try:
            subprocess.run(["cp", target, bak], check=False)
        except Exception:
            pass
        with open(target, 'w') as f:
            f.write(content)
        print(Fore.CYAN + f"[*] Wrote {target} (backup: {bak})")
    except Exception as e:
        print(Fore.RED + f"[!] Could not write {target}: {e}")
    return target


def flush_dns_cache():
    # Try resolvectl then systemd-resolve
    if which('resolvectl'):
        subprocess.run(['resolvectl', 'flush-caches'], check=False)
    elif which('systemd-resolve'):
        subprocess.run(['systemd-resolve', '--flush-caches'], check=False)


def apt_maintenance(dry_run=False, skip_upgrade=False):
    cmds = [
        ['apt', 'install', '-y', 'apt-transport-https'],
        ['apt', 'clean'],
        ['apt', 'update'],
        ['apt', 'dist-upgrade', '-y'],
    ]
    if dry_run:
        print(Fore.YELLOW + '[DRY-RUN] Would run apt maintenance commands:')
        for c in cmds:
            print('    ', ' '.join(c))
        return
    try:
        subprocess.run(cmds[0], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(cmds[1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(cmds[2], check=False)
        if not skip_upgrade:
            subprocess.run(cmds[3], check=False)
        else:
            print(Fore.CYAN + '[*] Skipping dist-upgrade as requested')
    except Exception as e:
        print(Fore.RED + f"[!] Apt operations encountered an issue: {e}")


def main():
    parser = argparse.ArgumentParser(description='Kali-Velox: Fast mirror selector and optimizer for Kali Rolling')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without making changes')
    parser.add_argument('--no-dns', action='store_true', help='Do not change DNS settings')
    parser.add_argument('--mirrors', type=int, default=3, help='Number of fastest mirrors to write (default: 3)')
    parser.add_argument('--max-workers', type=int, default=MAX_WORKERS, help='Number of threads for testing mirrors')
    parser.add_argument('--skip-upgrade', action='store_true', help='Do not run apt dist-upgrade')
    parser.add_argument('--backup-dir', type=str, default='', help='Directory to save backups')

    args = parser.parse_args()

    if not args.dry_run and os.geteuid() != 0:
        print(Fore.RED + "[!] Kali-Velox must be run as root unless using --dry-run. Use: sudo kalivelox or sudo python3 kalivelox.py")
        sys.exit(1)

    banner()
    print(Fore.YELLOW + f"[*] Options: mirrors={args.mirrors}, dry-run={args.dry_run}, no-dns={args.no_dns}, skip-upgrade={args.skip_upgrade}")

    mirrors = get_mirrors()
    if not mirrors:
        print(Fore.RED + "[!] No mirrors found. Exiting.")
        sys.exit(1)

    print(Fore.YELLOW + f"[*] Testing {len(mirrors)} mirrors (this may take a few seconds)...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.max_workers, len(mirrors))) as ex:
        for res in ex.map(test, mirrors):
            if res[2]:
                results.append((res[0], res[1]))

    if not results:
        print(Fore.RED + "[!] No reachable mirrors responded successfully. Exiting.")
        sys.exit(1)

    results.sort(key=lambda x: x[1])
    fastest = [r[0] for r in results[:args.mirrors]]
    print(Fore.GREEN + "[✓] Fastest mirrors:")
    for f in fastest:
        print("    - ", f)

    # Write sources.list (or dry-run)
    safe_write_sources(fastest, dry_run=args.dry_run, backup_dir=(args.backup_dir or None))

    # DNS handling
    dns_list = ['8.8.8.8', '1.1.1.1']
    if not args.no_dns:
        if is_systemd_resolved_managed():
            print(Fore.CYAN + "[*] systemd-resolved appears to manage /etc/resolv.conf; creating resolved drop-in instead of overwriting resolv.conf")
            write_systemd_resolved_conf(dns_list, dry_run=args.dry_run)
            if not args.dry_run:
                flush_dns_cache()
        else:
            write_resolv_conf(dns_list, dry_run=args.dry_run)
            if not args.dry_run:
                flush_dns_cache()
    else:
        print(Fore.CYAN + "[*] Skipping DNS changes as requested")

    apt_maintenance(dry_run=args.dry_run, skip_upgrade=args.skip_upgrade)

    print(Fore.GREEN + "[✓] Kali-Velox complete. Review output above for actions performed.")


if __name__ == '__main__':
    main()
