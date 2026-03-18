# osu! Beatmap Downloader

Downloads your most played beatmaps from osu! incrementally — skipping ones you've already downloaded, so you can run it multiple times without duplicates.

## How it works

1. On first run, asks for your osu! credentials and saves them to `config.json`
2. Fetches your most played beatmaps via the osu! API v2 (sorted by play count)
3. Skips beatmaps already listed in `downloaded.txt`
4. Downloads `.osz` files from the [catboy.best](https://catboy.best) mirror
5. Saves each beatmap ID to `downloaded.txt` right after a successful download

## Requirements

- Python 3.8+ (no external libraries required)
- An osu! OAuth application (instructions below)

## Setup

**1. Clone the repository**
```
git clone https://github.com/your-username/osu-beatmap-downloader.git
cd osu-beatmap-downloader
```

**2. Create an osu! OAuth application**

- Go to [osu! account settings](https://osu.ppy.sh/home/account/edit#oauth)
- Scroll down to **OAuth** and click **New OAuth Application**
- Give it any name (e.g. "Beatmap Downloader")
- Set the **Callback URL** to `http://localhost` (it won't actually be used)
- Click **Register application**
- Copy your **Client ID** and **Client Secret**

**3. Run the script**

```
python download_beatmaps.py
```

On first run, it will ask for:
- Your **Client ID** and **Client Secret** (from the step above)
- Your **osu! username**
- The **folder** where `.osz` files should be saved (press Enter for the default: `~/Downloads/osu!`)

These are saved to `config.json` so you won't be asked again.

## Usage

Each time you run the script:

1. It loads your saved config (or lets you reconfigure)
2. Fetches your full most-played list from the osu! API
3. Asks whether to download **with or without video** (no video = smaller files, faster)
4. Asks how many beatmaps to download this session
5. Downloads them one by one with live progress

Example output:
```
=== osu! Beatmap Downloader ===

Loaded config for user: yourname
Use saved config? (press Enter) or type 'reset' to reconfigure:

Authenticating with osu! API...
Logged in as: yourname (ID: 1234567)

Fetching most played beatmaps...
Total most played beatmaps: 1883
Already downloaded: 50
Remaining to download: 1833

Download with video? (y/n, default: n): n
Mode: no video (smaller files, faster downloads)

How many beatmaps do you want to download now? (max 1833): 30

Downloading 1/30 - Freedom Dive...
  3.1 MB / 3.1 MB (100%)
Downloading 2/30 - Some Removed Map...
  Attempt 1 failed: HTTP 404 - Beatmap not found on mirror (may have been removed via DMCA)
  Retrying in 3s...
  Attempt 2 failed: HTTP 404 - ...
  Skipping this beatmap.

=== Summary ===
Successfully downloaded: 29
Failed: 1

Files saved to: C:\Users\YourName\Downloads\osu!
```

## Importing into osu!

**osu!lazer:** Select the `.osz` files and drag them into the game window.

**osu!stable:** Double-click any `.osz` file while osu! is open, or drag them into the game window.

## Notes

- Credentials are stored in `config.json` — keep this file private, don't share it
- `downloaded.txt` tracks what's been downloaded — delete it or clear its contents to start fresh
- The script waits 1 second between downloads to avoid rate limiting
- Failed downloads are retried once before being skipped
- Files without video are typically 2–5 MB; with video, 10–30 MB
