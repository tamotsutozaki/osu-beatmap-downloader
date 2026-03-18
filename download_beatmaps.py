"""
download_beatmaps.py - Download your most played osu! beatmaps incrementally.
Usage: python download_beatmaps.py
"""

import urllib.request
import urllib.error
import json
import os
import sys
import time
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
DOWNLOADED_FILE = os.path.join(SCRIPT_DIR, "downloaded.txt")
MIRROR_URL = "https://catboy.best/d/{}"
API_BASE = "https://osu.ppy.sh"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def setup_config():
    print("=== First-time setup ===")
    print("You need an osu! OAuth application to use this tool.")
    print("Create one at: https://osu.ppy.sh/home/account/edit#oauth")
    print("(Set the callback URL to http://localhost — it won't be used)\n")

    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()
    username = input("Enter your osu! username: ").strip()

    default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "osu!")
    download_dir = input(f"Enter download folder (press Enter for default: {default_dir}): ").strip()
    if not download_dir:
        download_dir = default_dir

    cfg = {
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "download_dir": download_dir,
    }
    save_config(cfg)
    print(f"\nConfig saved to {CONFIG_FILE}\n")
    return cfg


# ---------------------------------------------------------------------------
# osu! API
# ---------------------------------------------------------------------------

def get_access_token(cfg):
    data = json.dumps({
        "client_id": int(cfg["client_id"]),
        "client_secret": cfg["client_secret"],
        "grant_type": "client_credentials",
        "scope": "public"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/oauth/token",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def api_get(endpoint, token):
    req = urllib.request.Request(
        f"{API_BASE}{endpoint}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_user_id(username, token):
    data = api_get(f"/api/v2/users/{username}/osu", token)
    return data["id"]


def fetch_most_played(user_id, token):
    beatmaps = []
    offset = 0
    limit = 50
    while True:
        batch = api_get(
            f"/api/v2/users/{user_id}/beatmapsets/most_played?limit={limit}&offset={offset}",
            token
        )
        if not batch:
            break
        for entry in batch:
            bs = entry.get("beatmapset", {})
            bsid = bs.get("id", entry.get("beatmap_id", 0))
            beatmaps.append({
                "beatmapset_id": bsid,
                "title": bs.get("title", str(bsid)),
                "count": entry.get("count", 0),
            })
        print(f"  Fetching most played... {len(beatmaps)} found", end="\r")
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.3)
    print()
    return beatmaps


# ---------------------------------------------------------------------------
# Download tracking
# ---------------------------------------------------------------------------

def load_downloaded():
    if not os.path.exists(DOWNLOADED_FILE):
        return set()
    with open(DOWNLOADED_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def mark_downloaded(beatmapset_id):
    with open(DOWNLOADED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{beatmapset_id}\n")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def format_size(nbytes):
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 * 1024:
        return f"{nbytes / 1024:.1f} KB"
    else:
        return f"{nbytes / (1024 * 1024):.1f} MB"


def describe_error(e):
    if isinstance(e, urllib.error.HTTPError):
        messages = {
            403: "Access denied by server",
            404: "Beatmap not found on mirror (may have been removed via DMCA)",
            429: "Rate limited — too many requests, server blocked temporarily",
            500: "Internal server error",
            502: "Mirror is down (Bad Gateway)",
            503: "Mirror under maintenance (Service Unavailable)",
        }
        desc = messages.get(e.code, f"HTTP error {e.code}")
        return f"HTTP {e.code} - {desc}"
    elif isinstance(e, urllib.error.URLError):
        reason = str(e.reason)
        if "timed out" in reason or "timeout" in reason:
            return "Timeout — server took too long to respond"
        elif "Connection refused" in reason:
            return "Connection refused by server"
        elif "Name or service not known" in reason or "getaddrinfo" in reason:
            return "No internet connection or DNS failure"
        return f"Connection error: {reason}"
    elif isinstance(e, TimeoutError) or "timed out" in str(e):
        return "Timeout — server took too long to respond"
    elif isinstance(e, OSError) and e.errno == 28:
        return "Disk full — not enough space to save the file"
    return str(e)


def download_osz(beatmapset_id, title, download_dir, no_video=True):
    url = MIRROR_URL.format(beatmapset_id)
    if no_video:
        url += "?noVideo"
    safe_title = sanitize_filename(title)
    filename = f"{beatmapset_id} - {safe_title}.osz"
    filepath = os.path.join(download_dir, filename)

    for attempt in range(1, 3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "osu-downloader/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = resp.headers.get("Content-Length")
                total_size = int(total_size) if total_size else None
                downloaded = 0
                chunks = []

                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = downloaded * 100 // total_size
                        print(f"  {format_size(downloaded)} / {format_size(total_size)} ({pct}%)", end="\r")
                    else:
                        print(f"  {format_size(downloaded)} downloaded...", end="\r")

            print()
            data = b"".join(chunks)

            if len(data) == 0:
                raise Exception("Empty file received")

            with open(filepath, "wb") as f:
                f.write(data)
            return True

        except Exception as e:
            print()
            msg = describe_error(e)
            if attempt == 1:
                print(f"  Attempt 1 failed: {msg}")
                print(f"  Retrying in 3s...")
                time.sleep(3)
            else:
                print(f"  Attempt 2 failed: {msg}")
                print(f"  Skipping this beatmap.")
                return False

    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== osu! Beatmap Downloader ===\n")

    cfg = load_config()
    if cfg is None:
        cfg = setup_config()
    else:
        print(f"Loaded config for user: {cfg['username']}")
        reset = input("Use saved config? (press Enter) or type 'reset' to reconfigure: ").strip().lower()
        if reset == "reset":
            cfg = setup_config()
        print()

    print("Authenticating with osu! API...")
    try:
        token = get_access_token(cfg)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    print("Fetching user ID...")
    try:
        user_id = get_user_id(cfg["username"], token)
    except Exception as e:
        print(f"Failed to fetch user: {e}")
        sys.exit(1)

    print(f"Logged in as: {cfg['username']} (ID: {user_id})\n")

    print("Fetching most played beatmaps...")
    beatmaps = fetch_most_played(user_id, token)
    total = len(beatmaps)
    print(f"Total most played beatmaps: {total}")

    downloaded = load_downloaded()
    print(f"Already downloaded: {len(downloaded)}")

    pending = [b for b in beatmaps if str(b["beatmapset_id"]) not in downloaded]
    print(f"Remaining to download: {len(pending)}\n")

    if not pending:
        print("All beatmaps have already been downloaded!")
        return

    while True:
        video_input = input("Download with video? (y/n, default: n): ").strip().lower()
        if video_input in ("y", "n", ""):
            break
        print("Please enter 'y' or 'n'.")
    no_video = video_input != "y"
    if no_video:
        print("Mode: no video (smaller files, faster downloads)\n")
    else:
        print("Mode: with video\n")

    while True:
        raw = input(f"How many beatmaps do you want to download now? (max {len(pending)}): ").strip()
        if raw.isdigit() and int(raw) > 0:
            count = min(int(raw), len(pending))
            break
        print("Please enter a valid number.")

    download_dir = cfg["download_dir"]
    os.makedirs(download_dir, exist_ok=True)

    to_download = pending[:count]
    success = 0
    failures = 0

    print()
    for i, bm in enumerate(to_download, 1):
        bid = bm["beatmapset_id"]
        title = bm["title"]
        print(f"Downloading {i}/{count} - {title}...")

        if download_osz(bid, title, download_dir, no_video):
            mark_downloaded(bid)
            success += 1
        else:
            failures += 1

        if i < count:
            time.sleep(1)

    print(f"\n=== Summary ===")
    print(f"Successfully downloaded: {success}")
    print(f"Failed: {failures}")
    print(f"\nFiles saved to: {download_dir}")


if __name__ == "__main__":
    main()
