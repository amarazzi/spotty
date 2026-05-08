"""Spotifyd lifecycle manager — detect, configure, and launch."""

from __future__ import annotations

import getpass
import shutil
import subprocess
import time
from pathlib import Path

DEVICE_NAME = "spotty"
_CONFIG_DIR = Path.home() / ".config" / "spotifyd"
_CONFIG_PATH = _CONFIG_DIR / "spotifyd.conf"


def is_installed() -> bool:
    return shutil.which("spotifyd") is not None


def is_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-f", "spotifyd"], capture_output=True).returncode == 0
    except Exception:
        return False


def setup_and_start(client_id: str, client_secret: str) -> bool:
    """Ensure spotifyd is configured and running. Returns True if running after this call."""
    if not is_installed():
        print(
            "\n  spotifyd not found — local audio playback unavailable.\n"
            "  To enable it, install spotifyd:\n"
            "    brew install spotifyd\n"
            "  Then restart spotty.\n"
        )
        return False

    if is_running():
        return True

    if not _CONFIG_PATH.exists():
        _prompt_and_write_config(client_id, client_secret)

    return _launch()


def _prompt_and_write_config(client_id: str, client_secret: str) -> None:
    print("\n  First-time spotifyd setup — enter your Spotify credentials")
    print("  (Spotify Premium required for playback)\n")
    username = input("  Spotify username / email: ").strip()
    password = getpass.getpass("  Spotify password: ")

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        f'[global]\n'
        f'username = "{username}"\n'
        f'password = "{password}"\n'
        f'backend = "rodio"\n'
        f'device_name = "{DEVICE_NAME}"\n'
        f'device_type = "computer"\n'
        f'client_id = "{client_id}"\n'
        f'client_secret = "{client_secret}"\n'
    )
    print(f"  Config saved → {_CONFIG_PATH}\n")


def _launch() -> bool:
    try:
        subprocess.Popen(
            ["spotifyd", "--no-daemon", "--config-path", str(_CONFIG_PATH)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Give spotifyd ~2 s to register with Spotify Connect
        time.sleep(2)
        return is_running()
    except Exception as e:
        print(f"\n  Could not start spotifyd: {e}\n")
        return False
