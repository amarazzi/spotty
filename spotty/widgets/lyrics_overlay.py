"""Lyrics modal — l to open, shows synced or static lyrics for the current track."""

from __future__ import annotations

import re
import time as _time

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label

from spotty.api import Track
from spotty import themes as _themes


def _parse_lrc(text: str) -> list[tuple[int, str]]:
    """Parse LRC timestamps into (time_ms, text) pairs sorted by time."""
    lines = []
    for line in text.splitlines():
        m = re.match(r"^\[(\d+):(\d+\.\d+)\](.*)", line)
        if m:
            minutes = int(m.group(1))
            seconds = float(m.group(2))
            content = m.group(3).strip()
            time_ms = int((minutes * 60 + seconds) * 1000)
            lines.append((time_ms, content))
    return sorted(lines, key=lambda x: x[0])


class LyricsOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "scroll_down", "", show=False),
        Binding("k", "scroll_up", "", show=False),
    ]

    def __init__(self, track: Track, **kwargs) -> None:
        super().__init__(**kwargs)
        self._track = track
        self._open_time = _time.monotonic()
        self._lines: list[tuple[int, str]] = []
        self._is_synced = False
        self._last_active_idx = -1
        self._autoscroll = True
        self._autoscroll_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="lyrics-container"):
            yield Label(f" {self._track.name}", id="modal-title")
            yield Label(f"[dim]{self._track.artist}[/dim]", id="modal-hint")
            with VerticalScroll(id="lyrics-scroll"):
                yield Label("", id="lyrics-text")

    def on_mount(self) -> None:
        self._load()

    def action_scroll_down(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_down()
        self._pause_autoscroll()

    def action_scroll_up(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_up()
        self._pause_autoscroll()

    def _pause_autoscroll(self) -> None:
        self._autoscroll = False
        if self._autoscroll_timer is not None:
            self._autoscroll_timer.stop()
        self._autoscroll_timer = self.set_timer(5.0, self._resume_autoscroll)

    def _resume_autoscroll(self) -> None:
        self._autoscroll = True

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True, name="lyrics")
    def _load(self) -> None:
        try:
            import syncedlyrics
            text = syncedlyrics.search(f"{self._track.name} {self._track.artist}")
        except Exception:
            self.app.call_from_thread(self._show_not_found)
            return

        if not text:
            self.app.call_from_thread(self._show_not_found)
            return

        lrc_lines = _parse_lrc(text)
        if lrc_lines:
            self._lines = lrc_lines
            self._is_synced = True
            self.app.call_from_thread(self._show_synced_initial)
        else:
            self.app.call_from_thread(self._show_plain, text)

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    def _show_not_found(self) -> None:
        self.query_one("#modal-hint", Label).update(
            f"[dim]{self._track.artist}[/dim]"
        )
        self.query_one("#lyrics-text", Label).update(
            "[dim]No lyrics found for this track[/dim]"
        )

    # ------------------------------------------------------------------
    # Static display (no timestamps)
    # ------------------------------------------------------------------

    def _show_plain(self, raw: str) -> None:
        lines = raw.splitlines()
        clean: list[str] = []
        for line in lines:
            stripped = re.sub(r"^\[\d+:\d+\.\d+\]", "", line).strip()
            if re.match(r"^\[.+:.+\]$", stripped):
                continue
            clean.append(stripped)
        self.query_one("#lyrics-text", Label).update("\n".join(clean).strip())
        self.query_one("#modal-hint", Label).update(
            f"[dim]{self._track.artist}  ·  j/k to scroll[/dim]"
        )

    # ------------------------------------------------------------------
    # Synced display (LRC timestamps)
    # ------------------------------------------------------------------

    def _show_synced_initial(self) -> None:
        self.query_one("#modal-hint", Label).update(
            f"[dim]{self._track.artist}  ·  synced  ·  j/k to scroll[/dim]"
        )
        self._sync_tick()
        self.set_interval(0.5, self._sync_tick)

    def _current_ms(self) -> int:
        elapsed = (_time.monotonic() - self._open_time) * 1000
        if self._track.is_playing:
            return int(self._track.progress_ms + elapsed)
        return self._track.progress_ms

    def _active_line_idx(self, current_ms: int) -> int:
        idx = 0
        for i, (time_ms, _) in enumerate(self._lines):
            if time_ms <= current_ms:
                idx = i
            else:
                break
        return idx

    def _sync_tick(self) -> None:
        if not self._lines:
            return
        current_ms = self._current_ms()
        active_idx = self._active_line_idx(current_ms)

        # Rebuild label only when the active line changes
        if active_idx != self._last_active_idx:
            self._last_active_idx = active_idx
            parts: list[str] = []
            for i, (_, text) in enumerate(self._lines):
                line = text or "♪"
                if i == active_idx:
                    parts.append(f"[bold {_themes.primary()}]{line}[/]")
                else:
                    parts.append(f"[#404040]{line}[/]")
            self.query_one("#lyrics-text", Label).update("\n".join(parts))

        if self._autoscroll:
            scroll = self.query_one("#lyrics-scroll", VerticalScroll)
            if scroll.size.height > 0:
                target_y = max(0, active_idx - scroll.size.height // 2)
                scroll.scroll_to(y=target_y, animate=False)
