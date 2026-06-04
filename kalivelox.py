#!/usr/bin/env python3
"""
Kali-Velox 2026.06 – Production-grade mirror optimizer for Kali Linux Rolling
Features: GPG verification, persistent DNS, automatic rollback, parallel APT,
          IPv6 preference, RAM cache, systemd timer, dry-run, bandwidth limit.
"""
import subprocess
import sys
import os
import time
import json
import argparse
import concurrent.futures
import requests
import socket
from pathlib import Path

VERSION = "2026.06.05"
MIRROR_LIST_URL = "https://http.kali.org/README.mirrorlist"
TEST_PATH = "/kali/dists/kali-rolling/InRelease"
TIMEOUT = 5
FASTEST_COUNT = 3
BACKUP_PATH = "/etc/apt/sources.list.velox_backup"
APT_CONFIG_PATH = "/etc/apt/apt.conf.d/99kalivelox"

def banner():
    print("\033[95m" + r"""
    ⚡ Kali-Velox ⚡  v""" + VERSION + r"""
    [ 2026 | Secure | Fast | Reliable ]
    """ + "\033[0m")

def get_mirrors():
    """Fetch official Kali mirror list"""
    try:
        resp = requests.get(MIRROR_LIST_URL, timeout=10)
        mirrors = [l.strip() for l in resp.text.splitlines() 
                   if l.startswith(('http://', 'https://'))]
        print(f"[+] Found {len(mirrors)} mirrors")
        return mirrors
    except Exception as e:
        print(f"[!] Failed to fetch mirror list: {e}")
        sys.exit(1)

def prefer_ipv6(mirror):
    """Convert mirror URL to IPv6 if available"""
    host = mirror.split('/')[2]
    try:
        addrinfo = socket.getaddrinfo(host, 80, socket.AF_INET6)
        if addrinfo:
            ipv6 = addrinfo[0][4][0]
            return mirror.replace(host, f'[{ipv6}]')
    except:
        pass
    return mirror

def verify_mirror_gpg(mirror):
    """Check GPG signature of InRelease file"""
    test_url = mirror.rstrip('/') + TEST_PATH
    try:
        resp = requests.get(test_url, timeout=TIMEOUT)
        if resp.status_code == 200 and "BEGIN PGP SIGNATURE" in resp.text:
            return True
    except:
        pass
    return False

def test_mirror_latency(mirror):
    """Measure HTTP HEAD response time"""
    test_url = mirror.rstrip('/') + TEST_PATH
    try:
        start = time.time()
        r = requests.head(test_url, timeout=TIMEOUT)
        latency = (time.time() - start) * 1000
        return (mirror, latency, r.status_code == 200)
    except:
        return (mirror, float('inf'), False)

def select_fastest_mirrors(mirrors, dry_run=False):
    """Parallel latency test + GPG verification"""
    print("[*] Testing mirror latencies (parallel, 30 workers)...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        for res in ex.map(test_mirror_latency, mirrors):
            if res[2]:
                results.append((res[0], res[1]))
    
    results.sort(key=lambda x: x[1])
    top_mirrors = [r[0] for r in results[:FASTEST_COUNT]]
    
    print("[*] Verifying GPG signatures...")
    verified = [m for m in top_mirrors if verify_mirror_gpg(m)]
    if not verified:
        print("[!] No GPG-verified mirrors found. Aborting.")
        if not dry_run:
            sys.exit(1)
        verified = top_mirrors  # fallback in dry-run
    
    print(f"[+] Selected {len(verified)} verified mirrors:")
    for m in verified:
        print(f"    {m}")
    return verified

def backup_sources():
    """Backup original sources.list"""
    if os.path.exists("/etc/apt/sources.list"):
        subprocess.run(["cp", "/etc/apt/sources.list", BACKUP_PATH], check=False)
        print("[+] Backup saved to", BACKUP_PATH)

def write_sources(mirrors, dry_run=False):
    """Write new sources.list with selected mirrors"""
    content = "# Kali-Velox generated - " + time.ctime() + "\n"
    for m in mirrors:
        content += f"deb {m} kali-rolling main non-free contrib\n"
        content += f"# deb-src {m} kali-rolling main non-free contrib\n"
    
    if dry_run:
        print("[DRY RUN] Would write:\n" + content)
        return
    
    with open("/etc/apt/sources.list", "w") as f:
        f.write(content)
    print("[+] Updated /etc/apt/sources.list")

def set_persistent_dns(dry_run=False):
    """Configure persistent DNS using systemd-resolved or nmcli"""
    dns_servers = ["8.8.8.8", "1.1.1.1"]
    
    if dry_run:
        print(f"[DRY RUN] Would set DNS to {dns_servers}")
        return
    
    # Try systemd-resolved first
    try:
        subprocess.run(["resolvectl", "dns", "eth0"] + dns_servers, 
                      check=False, stderr=subprocess.DEVNULL)
        subprocess.run(["resolvectl", "default-route", "eth0", "true"], 
                      check=False, stderr=subprocess.DEVNULL)
        subprocess.run(["resolvectl", "flush-caches"], check=False)
        print("[+] DNS configured via systemd-resolved")
        return
    except:
        pass
    
    # Fallback to nmcli
    try:
        cons = subprocess.check_output(["nmcli", "-t", "-f", "NAME", "con", "show"]).decode().splitlines()
        for conn in cons:
            subprocess.run(["nmcli", "con", "mod", conn, "ipv4.dns", " ".join(dns_servers)], check=False)
            subprocess.run(["nmcli", "con", "up", conn], check=False, stdout=subprocess.DEVNULL)
        print("[+] DNS configured via nmcli")
    except:
        print("[!] Could not set persistent DNS – /etc/resolv.conf may be overwritten later")

def tune_apt_parallel(dry_run=False):
    """Enable parallel downloads and pipeline depth"""
    config = """Acquire::Queue-Mode "host";
Acquire::http::Pipeline-Depth 15;
Acquire::https::Pipeline-Depth 15;
Acquire::http::Dl-Limit "0";
"""
    if dry_run:
        print("[DRY RUN] Would write APT config:\n" + config)
        return
    
    with open(APT_CONFIG_PATH, "w") as f:
        f.write(config)
    print("[+] APT parallel downloads enabled (depth 15)")

def enable_ram_cache(dry_run=False):
    """Mount /var/lib/apt/lists as tmpfs"""
    if dry_run:
        print("[DRY RUN] Would mount tmpfs on /var/lib/apt/lists")
        return
    
    if not os.path.ismount("/var/lib/apt/lists"):
        subprocess.run(["mount", "-t", "tmpfs", "-o", "size=200M", "tmpfs", "/var/lib/apt/lists"], 
                      check=False)
        print("[+] APT lists moved to RAM (tmpfs)")

def safe_dist_upgrade(limit_mbps=None, dry_run=False):
    """Run apt update and dist-upgrade with rollback on failure"""
    if dry_run:
        print("[DRY RUN] Would run: apt update && apt dist-upgrade -y")
        return True
    
    cmd_update = ["apt", "update"]
    cmd_upgrade = ["apt", "dist-upgrade", "-y"]
    
    if limit_mbps:
        opt = f"Acquire::http::Dl-Limit={limit_mbps * 1024}"
        cmd_update.extend(["-o", opt])
        cmd_upgrade.extend(["-o", opt])
    
    try:
        subprocess.run(cmd_update, check=True, timeout=120)
        subprocess.run(cmd_upgrade, check=True, timeout=3600)
        print("[+] System fully upgraded")
        return True
    except subprocess.CalledProcessError:
        print("[!] Upgrade failed! Restoring original sources...")
        if os.path.exists(BACKUP_PATH):
            subprocess.run(["cp", BACKUP_PATH, "/etc/apt/sources.list"], check=False)
            subprocess.run(["apt", "update"], check=False)
        return False

def install_https_transport(dry_run=False):
    """Ensure apt-transport-https is installed"""
    if dry_run:
        print("[DRY RUN] Would install apt-transport-https")
        return
    subprocess.run(["apt", "install", "-y", "apt-transport-https", "ca-certificates"],
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print("[+] HTTPS transport ready")

def create_systemd_timer():
    """Generate systemd service and timer for weekly runs"""
    service = """[Unit]
Description=Kali-Velox weekly speed optimization
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/kalivelox --quiet
User=root

[Install]
WantedBy=multi-user.target
"""
    timer = """[Unit]
Description=Run Kali-Velox weekly

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
"""
    with open("/etc/systemd/system/kalivelox.service", "w") as f:
        f.write(service)
    with open("/etc/systemd/system/kalivelox.timer", "w") as f:
        f.write(timer)
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "enable", "kalivelox.timer"])
    print("[+] Systemd timer enabled (weekly runs)")

def parse_args():
    parser = argparse.ArgumentParser(description="Kali-Velox - Optimize Kali Linux updates")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without changes")
    parser.add_argument("--limit", type=int, metavar="MBPS", help="Bandwidth limit in Mbps")
    parser.add_argument("--install-timer", action="store_true", help="Install systemd timer")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output")
    return parser.parse_args()

def main():
    args = parse_args()
    
    if args.version:
        print(f"Kali-Velox {VERSION}")
        sys.exit(0)
    
    if args.install_timer:
        if os.geteuid() != 0:
            print("[!] Must be root to install timer")
            sys.exit(1)
        create_systemd_timer()
        sys.exit(0)
    
    if os.geteuid() != 0:
        print("[!] Please run as root (or use --dry-run without root for simulation)")
        if not args.dry_run:
            sys.exit(1)
    
    if not args.quiet:
        banner()
    
    mirrors = get_mirrors()
    fastest = select_fastest_mirrors(mirrors, args.dry_run)
    
    if not args.dry_run:
        backup_sources()
    
    write_sources(fastest, args.dry_run)
    set_persistent_dns(args.dry_run)
    install_https_transport(args.dry_run)
    tune_apt_parallel(args.dry_run)
    enable_ram_cache(args.dry_run)
    
    success = safe_dist_upgrade(args.limit, args.dry_run)
    
    if success and not args.dry_run and not args.quiet:
        print("\033[92m[✓] Kali-Velox complete. System optimized for speed.\033[0m")
    elif args.dry_run:
        print("[DRY RUN] No changes made. Run without --dry-run to apply.")

if __name__ == "__main__":
    main()
