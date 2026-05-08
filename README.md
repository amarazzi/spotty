# spotty

A Spotify TUI built in Python using Textual and the Spotify Web API.

![spotty screenshot](screenshot.png)

## Features

- **Now playing** — full-screen view with album art (Sixel/Kitty/half-block depending on terminal), track info, and a real-time progress bar with `━━━●━━━` cursor
- **Search** — `/` opens a search overlay; type, hit Enter, select a track to play
- **Playlists** — `l` opens your playlists; select one to start playing it
- **Recently played** — `r` shows your listening history
- **Playback controls** — `space` play/pause, `n` next, `p` previous, `+`/`-` volume
- **Auto device activation** — if no device is active, spotty finds one and transfers playback automatically
- **spotifyd integration** — optional local audio daemon so spotty works completely standalone (no phone or desktop app needed)

## Requirements

- Python 3.11+
- Spotify Premium account (required for playback control via the Web API)
- A Spotify Developer app (free) — [create one here](https://developer.spotify.com/dashboard)

## Installation

```bash
git clone https://github.com/amarazzi/spotty
cd spotty
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy the env template and fill in your credentials:

```bash
cp .env.example .env
```

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

> In the Spotify Developer Dashboard, add `http://127.0.0.1:8888/callback` as a Redirect URI.

## Running

```bash
source .venv/bin/activate
spotty
```

First run opens a browser for Spotify OAuth. Log in, copy the redirect URL from the address bar, paste it in the terminal. Token is cached at `~/.spotify_cache` — you only authenticate once.

## Local audio (spotifyd)

To use spotty without any Spotify app running:

```bash
brew install spotifyd
```

On next launch, spotty detects spotifyd, asks for your Spotify username/password once, writes `~/.config/spotifyd/spotifyd.conf`, and starts it automatically. From then on, spotty is fully self-contained.

## Keybindings

| Key | Action |
|---|---|
| `space` | Play / Pause |
| `n` | Next track |
| `p` | Previous track |
| `+` / `=` | Volume +5% |
| `-` | Volume −5% |
| `/` | Search |
| `l` | Playlists |
| `r` | Recently played |
| `q` | Quit |

## Stack

- [Textual](https://github.com/Textualize/textual) — TUI framework
- [spotipy](https://github.com/spotipy-dev/spotipy) — Spotify Web API + OAuth
- [textual-image](https://github.com/lnqs/textual-image) — Sixel/Kitty album art
- [rich-pixels](https://github.com/darrenburns/rich-pixels) — half-block fallback
- [Pillow](https://python-pillow.org/) — image processing
- [httpx](https://www.python-httpx.org/) — async HTTP for cover art
- [spotifyd](https://github.com/Spotifyd/spotifyd) — optional local Spotify Connect daemon
