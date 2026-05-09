"""Google Cast discovery and Spotify Connect wake-up."""

from __future__ import annotations

import threading
import time

try:
    import pychromecast
    from pychromecast.controllers import BaseController
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

SPOTIFY_APP_ID = "CC32E753"
SPOTIFY_NAMESPACE = "urn:x-cast:com.spotify.chromecast.secure.v1"

_CAST_TYPE_LABEL = {
    "cast": "Chromecast",
    "audio": "Speaker",
    "group": "Group",
}


class _SpotifyController(BaseController):
    """Sends Spotify credentials to a Cast device to wake it into Spotify Connect."""

    def __init__(self, access_token: str) -> None:
        super().__init__(SPOTIFY_NAMESPACE, SPOTIFY_APP_ID)
        self._token = access_token
        self._launched = threading.Event()

    def receive_message(self, message, data: dict) -> bool:
        if data.get("type") in ("setCredentialsResponse", "setCredentials"):
            self._launched.set()
        return True

    def launch_spotify(self, timeout: float = 8.0) -> bool:
        ready = threading.Event()

        def _on_launched() -> None:
            self.send_message({"type": "setCredentials", "credentials": self._token})
            ready.set()

        self.launch(callback_function=_on_launched)
        return ready.wait(timeout=timeout)


def discover(timeout: float = 4.0) -> list[dict]:
    """Return Cast devices found on the local network (excludes already-known Spotify devices)."""
    if not _AVAILABLE:
        return []
    try:
        cast_infos, browser = pychromecast.discovery.discover_chromecasts(timeout=timeout)
        pychromecast.stop_discovery(browser)
        devices = []
        for info in cast_infos:
            label = _CAST_TYPE_LABEL.get(getattr(info, "cast_type", ""), "Cast")
            devices.append({
                "id": str(info.uuid),
                "name": info.friendly_name,
                "type": label,
                "is_active": False,
                "is_restricted": False,
                "volume_percent": None,
                "_cast_info": info,
            })
        return devices
    except Exception:
        return []


def wake_and_connect(cast_info, access_token: str, api, timeout: float = 30.0) -> str | None:
    """
    Launch Spotify on a Cast device, wait for it to appear in Spotify Connect,
    and return its device_id. Returns None on failure.
    """
    if not _AVAILABLE or not access_token:
        return None
    try:
        import zeroconf as _zc
        zconf = _zc.Zeroconf()

        # Snapshot current device IDs to detect new arrivals
        try:
            before_ids = {d["id"] for d in api.available_devices()}
        except Exception:
            before_ids = set()

        cast = pychromecast.get_chromecast_from_cast_info(cast_info, zconf)
        cast.wait(timeout=6)

        ctrl = _SpotifyController(access_token)
        cast.register_handler(ctrl)
        ctrl.launch_spotify(timeout=8)

        # Give the Cast device a moment to register with Spotify
        time.sleep(3.0)

        target_words = set(cast_info.friendly_name.lower().split())

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                current = api.available_devices()

                # 1. Name match — works even if the device ID was already known
                for d in current:
                    dname = d.get("name", "").lower()
                    dwords = set(dname.split())
                    if target_words & dwords:  # any word in common
                        zconf.close()
                        return d["id"]

                # 2. Any brand-new device ID
                for d in current:
                    if d["id"] not in before_ids:
                        zconf.close()
                        return d["id"]

            except Exception:
                pass
            time.sleep(2.5)

        zconf.close()
        return None
    except Exception:
        return None


def cast_url(cast_info, url: str) -> bool:
    """Tell a Cast device to play an HTTP audio stream URL."""
    if not _AVAILABLE:
        return False
    try:
        import zeroconf as _zc
        zconf = _zc.Zeroconf()
        cast = pychromecast.get_chromecast_from_cast_info(cast_info, zconf)
        cast.wait(timeout=8)
        mc = cast.media_controller
        mc.play_media(url, "audio/mpeg")
        mc.block_until_active(timeout=10)
        zconf.close()
        return True
    except Exception:
        try:
            zconf.close()
        except Exception:
            pass
        return False


def get_access_token(sp_client) -> str | None:
    """Extract a fresh (auto-refreshed) access token from a spotipy client."""
    try:
        # get_access_token auto-refreshes if expired
        return sp_client.auth_manager.get_access_token(as_dict=False)
    except Exception:
        try:
            info = sp_client.auth_manager.get_cached_token()
            return info["access_token"] if info else None
        except Exception:
            return None
