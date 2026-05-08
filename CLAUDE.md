# spotty

A Spotify TUI built in Python using Textual and the Spotify Web API.

## Project structure

```
spotty/
├── pyproject.toml          # deps + entry point (`spotty` command)
├── .env                    # credentials (not committed)
├── .env.example            # template
├── spotty/
│   ├── __main__.py         # entry point: auth → launch SpottyApp
│   ├── auth.py             # OAuth 2.0 paste-URL flow, token cached at ~/.spotify_cache
│   ├── api.py              # SpotifyAPI wrapper + Track/Playlist dataclasses
│   ├── app.py              # SpottyApp: keybindings, modal management, safe API calls
│   ├── spotty.tcss         # Textual CSS — Spotify dark (#121212 bg, #1DB954 green)
│   └── widgets/
│       ├── now_playing.py      # Full-screen: ASCII art (52×22), track info, progress, hints
│       ├── search_overlay.py   # ModalScreen: search input + track results
│       ├── playlists_overlay.py # ModalScreen: user playlists list
│       └── home_overlay.py     # ModalScreen: Spotify featured playlists
```

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

## Spotify Dashboard setup

1. developer.spotify.com/dashboard → Create app
2. Redirect URI: `http://127.0.0.1:8888/callback`
3. Copy Client ID + Secret to `.env`

## UI design (iteration 2)

**Philosophy**: now-playing-centric. The app shows what's playing. Everything else is on demand via overlays.

**Base view** (`NowPlaying` widget):
- Full-screen, centered
- ASCII art (52×22, loaded async via worker thread)
- Track name, artist, album
- Progress bar with elapsed/total time
- Hint bar at bottom showing available keys

**Overlays** (ModalScreen, Esc to close, dim background):
- `/` → `SearchOverlay`: type + Enter to search, j/k to navigate, Enter to play
- `l` → `PlaylistsOverlay`: user playlists, Enter to play
- `r` → `HomeOverlay`: Spotify featured playlists, Enter to play

**Keybindings**:
| Key | Action |
|---|---|
| `space` | Play/Pause |
| `n` | Next track |
| `p` | Previous track |
| `+` / `-` | Volume ±5% |
| `/` | Search overlay |
| `l` | Playlists overlay |
| `r` | Home overlay |
| `q` | Quit |

## Key modules

- **`auth.py`** — `get_spotify_client()`: paste-URL OAuth flow. No local server needed.
- **`api.py`** — `SpotifyAPI`: `current_track()`, `play_pause()`, `next/previous_track()`, `set_volume()`, `playlists()`, `playlist_tracks()`, `play_playlist()`, `search_tracks()`, `play_track()`, `home_content()`
- **`app.py`** — `_safe_api(fn)`: wraps all calls, shows toast on `NO_ACTIVE_DEVICE` / 403 / other errors. Refresh timer every 3s.

## Tech stack

- **Textual** ≥ 0.89 — TUI framework (ModalScreen for overlays, workers for async)
- **spotipy** ≥ 2.24 — Spotify API + OAuth
- **Pillow** ≥ 11 — album cover → ASCII art (PIL resize + grayscale)
- **httpx** — cover image download in worker thread
- **python-dotenv** — `.env` loading

## Notes

- Spotify Premium required for playback control
- ASCII art loads async (worker thread) — UI never blocks
- `NO_ACTIVE_DEVICE` shows as a warning toast, not a crash
- OAuth redirect URI must be `http://127.0.0.1:8888/callback` (not localhost, not https)
