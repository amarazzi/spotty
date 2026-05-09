"""Shared message types for inter-widget communication."""
from __future__ import annotations
from textual.message import Message


class AddToQueue(Message):
    def __init__(self, track_id: str) -> None:
        super().__init__()
        self.track_id = track_id
