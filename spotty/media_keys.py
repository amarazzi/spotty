"""macOS media key interception via CGEventTap + Now Playing info center."""

from __future__ import annotations

import threading
from typing import Callable

_handlers: list = []  # strong refs to prevent GC

# NX aux key codes
_PLAY  = 16
_NEXT  = 19  # NX_KEYTYPE_FAST
_PREV  = 20  # NX_KEYTYPE_REWIND

# NSEventType for system-defined events (media keys use this)
_NS_SYSTEM_DEFINED = 14


def setup(
    on_play_pause: Callable,
    on_next: Callable,
    on_prev: Callable,
) -> bool:
    """
    Intercept macOS media keys via CGEventTap.
    Requires Accessibility permission for the terminal app:
      System Settings → Privacy & Security → Accessibility → enable Terminal/iTerm2
    Returns True if the tap was created successfully.
    """
    try:
        from Quartz import (  # type: ignore
            CGEventTapCreate, CGEventTapEnable,
            CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
            CFRunLoopGetCurrent, CFRunLoopRun,
            kCGSessionEventTap, kCGHeadInsertEventTap,
            kCGEventTapOptionDefault, kCFRunLoopCommonModes,
        )
        from AppKit import NSEvent  # type: ignore
    except ImportError:
        return False

    event_mask = 1 << _NS_SYSTEM_DEFINED

    def _callback(proxy, event_type, event, refcon):
        if event_type == _NS_SYSTEM_DEFINED:
            try:
                ns = NSEvent.eventWithCGEvent_(event)
                if ns and ns.subtype() == 8:
                    data = ns.data1()
                    key_code  = (data & 0xFFFF0000) >> 16
                    key_state = (data & 0x0000FF00) >> 8
                    if key_state == 0x0A:  # key-down only
                        if key_code == _PLAY:
                            on_play_pause()
                            return None   # consume — don't pass to Apple Music
                        elif key_code == _NEXT:
                            on_next()
                            return None
                        elif key_code == _PREV:
                            on_prev()
                            return None
            except Exception:
                pass
        return event

    _handlers.append(_callback)

    def _run() -> None:
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            event_mask,
            _callback,
            None,
        )
        if not tap:
            # Accessibility permission not granted — tap creation fails silently
            return
        src = CFMachPortCreateRunLoopSource(None, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), src, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)
        CFRunLoopRun()

    t = threading.Thread(target=_run, daemon=True, name="media-keys")
    t.start()
    return True


def update_now_playing(
    title: str,
    artist: str,
    duration_ms: int,
    progress_ms: int,
    is_playing: bool,
) -> None:
    """Push track info to macOS Now Playing / Control Center."""
    try:
        from MediaPlayer import (  # type: ignore
            MPNowPlayingInfoCenter,
            MPMediaItemPropertyTitle,
            MPMediaItemPropertyArtist,
            MPMediaItemPropertyPlaybackDuration,
            MPNowPlayingInfoPropertyElapsedPlaybackTime,
            MPNowPlayingInfoPropertyPlaybackRate,
            MPNowPlayingPlaybackStatePlaying,
            MPNowPlayingPlaybackStatePaused,
        )
    except ImportError:
        return
    try:
        center = MPNowPlayingInfoCenter.defaultCenter()
        center.setNowPlayingInfo_({
            MPMediaItemPropertyTitle: title,
            MPMediaItemPropertyArtist: artist,
            MPMediaItemPropertyPlaybackDuration: duration_ms / 1000.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: progress_ms / 1000.0,
            MPNowPlayingInfoPropertyPlaybackRate: 1.0 if is_playing else 0.0,
        })
        center.setPlaybackState_(
            MPNowPlayingPlaybackStatePlaying if is_playing
            else MPNowPlayingPlaybackStatePaused
        )
    except Exception:
        pass
