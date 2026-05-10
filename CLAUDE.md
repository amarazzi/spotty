# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# spotty

A Spotify TUI built in Python using Textual and the Spotify Web API.

## Running

```bash
source .venv/bin/activate
spotty
```

First run opens browser for Spotify OAuth (paste-URL flow). Token cached at `~/.spotify_cache`.

## Environment variables

| Variable | Description |
|---|---|
| `SPOTIFY_CLIENT_ID` | From Spotify Developer Dashboard |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |
| `SPOTIFY_REDIRECT_URI` | Must match dashboard; use `http://127.0.0.1:8888/callback` |

## Architecture

**Philosophy**: now-playing-centric. Everything is on demand via overlays (ModalScreen).

### Core modules

- **`api.py`** — `SpotifyAPI` wrapper around spotipy. Stores `_last_device_id` from every `current_track()` response. All playback methods accept an optional `device_id`.
- **`app.py`** — `SpottyApp`: refresh timer every 3s, `_safe_api(fn)` wraps all calls (handles `NO_ACTIVE_DEVICE`, 403, network errors). Manages `_device_id` (where commands are sent) separately from `api._last_device_id` (what Spotify reports as active).
- **`spotifyd_manager.py`** — detects/launches spotifyd as a local Spotify Connect device named `"spotty"`.
- **`cast_helper.py`** — pychromecast: discovers Cast devices on LAN, `cast_url()` to start HTTP stream playback. Always calls `cast.disconnect(blocking=False)` after use to avoid blocking process exit.
- **`librespot_bridge.py`** — `LibrespotBridge`: librespot → ffmpeg → HTTPServer pipeline for casting. `stop()` closes `audio_pipe` first (unblocks `pipe.read()` in the HTTP handler) then kills processes. `force_stop()` is non-blocking for use in `on_unmount`.
- **`track_cache.py`** — persists last track to `~/.cache/spotty/last_track.json` for instant display on startup.
- **`messages.py`** — custom Textual messages (e.g. `AddToQueue`).

### Device management (critical)

`app._device_id` tracks where commands should go. It is synced from `api._last_device_id` on every refresh **only when no bridge is active** (`_active_bridge is None`). While casting via the librespot bridge, `_device_id` is set exclusively by `_bridge_cast_bg` and must not be overwritten by transient Spotify state (Spotify may report a different device as active after a pause).

### Cast bridge flow

`d` → DevicesOverlay → if Cast device: `_bridge_cast_bg` (worker thread):
1. Start librespot (`--backend pipe`) → ffmpeg → HTTPServer
2. `cast_url()` tells Google Home to play the HTTP stream URL
3. Wait for `'spotty-bridge'` to appear in Spotify Connect
4. `transfer_playback(bridge_device_id, force_play=True)` → librespot receives audio
5. Store `_cast_info` + `_stream_url` for re-cast on track skip

When N is pressed while casting, a re-cast is triggered after 2.5s (librespot has a brief audio gap between tracks that causes Google Home to disconnect from the stream).

### Worker pattern

All blocking operations use `@work(thread=True)`. The main thread never blocks. `call_from_thread()` updates UI from workers. `exclusive=True` workers cancel pending instances of the same name.

### CSS class names (Textual)

- Keyboard selection: `ListItem.-highlight` (single dash — set via `set_class(value, "-highlight")`)
- Mouse hover: `ListItem:hover` pseudo-class (`:hover` works; `-hovered` class is also set)
- Do NOT use `.--highlight` (double dash) — that's wrong for this Textual version.

## Keybindings

| Key | Action |
|---|---|
| `space` | Play/Pause |
| `n` / `p` | Next / Previous |
| `+` / `-` | Volume ±5% |
| `[` / `]` | Seek ±10s |
| `/` | Search |
| `o` | Playlists |
| `r` | Home/Discover |
| `l` | Lyrics |
| `u` | Queue |
| `d` | Devices |
| `s` | Shuffle |
| `x` | Repeat |
| `h` | Like/Unlike |
| `f` | Liked Songs |
| `i` | Artist info |
| `?` | Help |
| `q` | Quit |

## Tech stack

- **Textual** ≥ 0.89 — TUI framework
- **spotipy** ≥ 2.24 — Spotify API + OAuth
- **Pillow** ≥ 11 — album cover → ASCII art
- **pychromecast** ≥ 14 — Cast device discovery and control
- **syncedlyrics** — lyrics fetching
- **librespot** + **ffmpeg** (external, brew) — Cast audio bridge

## Notes

- Spotify Premium required for playback control
- OAuth redirect URI must be `http://127.0.0.1:8888/callback` (not localhost, not https)
- librespot credentials cached at `~/.spotty_librespot_cache/credentials.json`
