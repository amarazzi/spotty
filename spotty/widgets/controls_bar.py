"""Bottom bar: progress, volume, playback state."""

from textual.app import ComposeResult
from textual.widgets import Label, ProgressBar, Static


class ControlsBar(Static):
    def compose(self) -> ComposeResult:
        yield Label("", id="controls-left")
        yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress")
        yield Label("", id="controls-right")

    def update(self, track=None, volume: int = 50) -> None:
        if track is None:
            self.query_one("#controls-left", Label).update("[dim]No active device[/dim]")
            self.query_one("#controls-right", Label).update(f"[dim]vol {volume}%[/dim]")
            self.query_one(ProgressBar).update(progress=0)
            return

        state = "▶" if track.is_playing else "⏸"
        elapsed = track.progress_ms // 1000
        total = track.duration_ms // 1000
        e_min, e_sec = divmod(elapsed, 60)
        t_min, t_sec = divmod(total, 60)

        self.query_one("#controls-left", Label).update(
            f" {state}  [bold]{track.name}[/bold]  [dim]{e_min}:{e_sec:02d}[/dim]"
        )
        self.query_one("#controls-right", Label).update(
            f"[dim]{t_min}:{t_sec:02d}  vol {volume}%[/dim] "
        )
        pct = int(track.progress_ms / track.duration_ms * 100) if track.duration_ms else 0
        self.query_one(ProgressBar).update(progress=pct)
