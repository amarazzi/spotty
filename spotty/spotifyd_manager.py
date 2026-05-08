"""Spotifyd lifecycle manager — detect, authenticate, and launch."""

from __future__ import annotations

import atexit
import shutil
import subprocess
from pathlib import Path

DEVICE_NAME = "spotty"
_CACHE_DIR = Path.home() / ".cache" / "spotifyd"
_CREDENTIALS = _CACHE_DIR / "oauth" / "credentials.json"


def is_installed() -> bool:
    return shutil.which("spotifyd") is not None


def is_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-f", "spotifyd"], capture_output=True).returncode == 0
    except Exception:
        return False


def setup_and_start() -> bool:
    """Ensure spotifyd is authenticated and running. Returns True if running after this call."""
    if not is_installed():
        print(
            "\n  spotifyd not found — local audio playback unavailable.\n"
            "  To enable it:  brew install spotifyd\n"
            "  Then restart spotty.\n"
        )
        return False

    if is_running():
        atexit.register(stop)
        return True

    if not _CREDENTIALS.exists():
        _authenticate()

    return _launch()


def _authenticate() -> None:
    """Run spotifyd's one-time OAuth login (opens browser, caches token)."""
    print("\n  First-time spotifyd setup — a browser will open for Spotify login.")
    print("  Log in and authorise spotty, then come back here.\n")
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["spotifyd", "authenticate", "--cache-path", str(_CACHE_DIR)],
        check=False,
    )
    print()


def stop() -> None:
    """Kill spotifyd if it's running."""
    try:
        subprocess.run(["pkill", "-f", "spotifyd"], capture_output=True)
    except Exception:
        pass


def _launch() -> bool:
    try:
        subprocess.Popen(
            [
                "spotifyd", "--no-daemon",
                "--backend", "portaudio",
                "--device-name", DEVICE_NAME,
                "--cache-path", str(_CACHE_DIR),
                "--disable-discovery=true",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Don't sleep here — the TUI polls for the device in a background worker.
        atexit.register(stop)
        return True
    except Exception as e:
        print(f"\n  Could not start spotifyd: {e}\n")
        return False
