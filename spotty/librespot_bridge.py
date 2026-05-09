"""
librespot → ffmpeg → HTTP stream → Chromecast bridge.

Requirements:  brew install librespot && brew install ffmpeg

First run: librespot registers as 'spotty-bridge' in Spotify Connect.
  Open Spotify on your phone → select 'spotty-bridge' once.
  Credentials are cached; every subsequent cast is automatic.
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

BRIDGE_NAME = "spotty-bridge"
CACHE_DIR = os.path.expanduser("~/.spotty_librespot_cache")
CREDS_FILE = os.path.join(CACHE_DIR, "credentials.json")


def is_librespot_installed() -> bool:
    try:
        r = subprocess.run(["librespot", "--version"], capture_output=True, timeout=3)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_ffmpeg_installed() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def has_credentials() -> bool:
    return os.path.exists(CREDS_FILE)


class _StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        pipe = self.server.audio_pipe
        try:
            while True:
                chunk = pipe.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, *args):
        pass


class LibrespotBridge:
    """Manages a librespot + ffmpeg + HTTP stream for one Cast device session."""

    def __init__(self) -> None:
        self._librespot: subprocess.Popen | None = None
        self._ffmpeg: subprocess.Popen | None = None
        self._server: HTTPServer | None = None
        self._port: int | None = None

    def link(self) -> subprocess.Popen | None:
        """
        Start librespot in zeroconf mode so the user can link credentials once.
        The device appears as 'spotty-bridge' in the Spotify app.
        Volume is set to 0 to silence accidental playback during linking.
        """
        os.makedirs(CACHE_DIR, exist_ok=True)
        try:
            return subprocess.Popen(
                [
                    "librespot",
                    "--cache", CACHE_DIR,
                    "--name", BRIDGE_NAME,
                    "--device-type", "speaker",
                    "--initial-volume", "0",
                    "--quiet",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return None

    def start(self) -> str | None:
        """
        Start the full pipeline (requires cached credentials).
        Returns HTTP stream URL like 'http://192.168.x.x:PORT/stream.mp3', or None.
        """
        if not has_credentials():
            return None

        self._port = self._free_port()
        os.makedirs(CACHE_DIR, exist_ok=True)

        try:
            self._librespot = subprocess.Popen(
                [
                    "librespot",
                    "--cache", CACHE_DIR,
                    "--name", BRIDGE_NAME,
                    "--bitrate", "320",
                    "--backend", "pipe",
                    "--device-type", "speaker",
                    "--disable-audio-cache",
                    "--quiet",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return None

        # Give librespot a moment; if it exits immediately credentials are bad
        time.sleep(1.2)
        if self._librespot.poll() is not None:
            self._librespot = None
            return None

        try:
            self._ffmpeg = subprocess.Popen(
                [
                    "ffmpeg", "-y", "-loglevel", "quiet",
                    "-f", "s16le", "-ar", "44100", "-ac", "2",
                    "-i", "pipe:0",
                    "-acodec", "libmp3lame", "-b:a", "192k",
                    "-f", "mp3", "pipe:1",
                ],
                stdin=self._librespot.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self._librespot.kill()
            self._librespot = None
            return None

        server = HTTPServer(("0.0.0.0", self._port), _StreamHandler)
        server.audio_pipe = self._ffmpeg.stdout
        self._server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()

        return f"http://{self._local_ip()}:{self._port}/stream.mp3"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        for proc in (self._ffmpeg, self._librespot):
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self._ffmpeg = None
        self._librespot = None

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    @staticmethod
    def _local_ip() -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
            except Exception:
                return "127.0.0.1"
