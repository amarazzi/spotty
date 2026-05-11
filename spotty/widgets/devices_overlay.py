"""Devices modal — d to open, lists Spotify Connect + Google Cast devices."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import SpotifyAPI
from spotty import cast_helper
from spotty import themes as _themes

_TYPE_ICON = {
    "Computer": "⊡",
    "Smartphone": "▣",
    "Speaker": "♪",
    "TV": "▣",
    "CastVideo": "▸",
    "CastAudio": "♪",
    "Chromecast": "▸",
    "Group": "♪",
    "Automobile": "⊡",
}


class DevicesOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
        Binding("r", "refresh", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._devices: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Devices", id="modal-title")
            yield Label("[dim]Scanning…[/dim]", id="modal-hint")
            yield ListView(id="home-list")

    def on_mount(self) -> None:
        self._load()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_refresh(self) -> None:
        self._devices = []
        self.query_one(ListView).clear()
        self.query_one("#modal-hint", Label).update("[dim]Scanning…[/dim]")
        self._load()

    @work(thread=True, exclusive=True, name="devices")
    def _load(self) -> None:
        # Phase 1: Spotify Connect devices (fast)
        try:
            spotify_devices = self.api.available_devices()
        except Exception:
            spotify_devices = []

        self._devices = list(spotify_devices)
        self.app.call_from_thread(self._populate, self._devices, scanning=True)

        # Phase 2: Cast devices on local network (~4s scan)
        cast_devices = cast_helper.discover(timeout=4.0)

        # Only add Cast devices not already showing in Spotify Connect
        known_names = {d.get("name", "").lower() for d in spotify_devices}
        new_cast = [d for d in cast_devices if d["name"].lower() not in known_names]

        if new_cast:
            self._devices = list(spotify_devices) + new_cast

        self.app.call_from_thread(self._populate, self._devices, scanning=False)

    def _populate(self, devices: list[dict], scanning: bool = False) -> None:
        lv = self.query_one(ListView)
        lv.clear()

        scan_suffix = "  [dim]· scanning Cast…[/dim]" if scanning else "  [dim]· r to refresh[/dim]"

        if not devices:
            if not scanning:
                self.query_one("#modal-hint", Label).update(
                    "[dim]No devices found · r to scan again[/dim]"
                )
            return

        count = len(devices)
        self.query_one("#modal-hint", Label).update(
            f"[dim]{count} device{'s' if count != 1 else ''} · Enter to switch{scan_suffix}[/dim]"
        )

        for d in devices:
            is_cast = "_cast_info" in d
            icon = _TYPE_ICON.get(d.get("type", ""), "·")
            name = d.get("name", "Unknown")
            dtype = d.get("type", "")
            is_active = d.get("is_active", False)
            vol = d.get("volume_percent")
            vol_str = f"  [dim]{vol}%[/dim]" if vol is not None else ""

            if is_active:
                p = _themes.primary()
                label = (
                    f"[bold {p}]{icon}  {name}[/bold {p}]"
                    f"  [dim {p}]{dtype}[/dim {p}]"
                    f"  [{p}]← playing[/{p}]{vol_str}"
                )
            elif is_cast:
                label = (
                    f"[#606060]▸[/#606060]  [bold]{name}[/bold]"
                    f"  [dim]{dtype}[/dim]"
                )
            else:
                label = (
                    f"[#606060]{icon}[/#606060]  [bold]{name}[/bold]"
                    f"  [dim]{dtype}[/dim]{vol_str}"
                )
            lv.append(ListItem(Label(label)))

        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._devices):
            self.dismiss(self._devices[idx])
        else:
            self.dismiss(None)
