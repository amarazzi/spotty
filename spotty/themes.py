"""Theme definitions and CSS generation for spotty."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    bg: str        # screen background
    surface: str   # modal / overlay background
    surface2: str  # list background
    surface3: str  # input background
    surface4: str  # hover / selected background
    primary: str   # accent color
    text: str      # primary text
    subtext1: str  # lyrics / secondary text
    subtext2: str  # times, album, stats
    subtext3: str  # list items, hints, very muted
    separator: str # divider lines
    border: str    # toast / subtle border
    toast_bg: str  # toast background


THEMES: list[Theme] = [
    Theme(
        "spotify", "Spotify",
        bg="#121212", surface="#1c1c1c", surface2="#141414",
        surface3="#242424", surface4="#2a2a2a",
        primary="#1DB954", text="#FFFFFF",
        subtext1="#B3B3B3", subtext2="#909090", subtext3="#535353",
        separator="#282828", border="#3a3a3a", toast_bg="#1e1e1e",
    ),
    Theme(
        "dracula", "Dracula",
        bg="#282a36", surface="#2d2f3e", surface2="#252633",
        surface3="#373847", surface4="#44475a",
        primary="#bd93f9", text="#f8f8f2",
        subtext1="#bbbcc8", subtext2="#9a9bab", subtext3="#6272a4",
        separator="#383a4a", border="#44475a", toast_bg="#21222c",
    ),
    Theme(
        "nord", "Nord",
        bg="#2e3440", surface="#3b4252", surface2="#333844",
        surface3="#404859", surface4="#434c5e",
        primary="#88c0d0", text="#eceff4",
        subtext1="#d8dee9", subtext2="#aab0bc", subtext3="#7b8394",
        separator="#3b4252", border="#4c566a", toast_bg="#2a3040",
    ),
    Theme(
        "gruvbox", "Gruvbox",
        bg="#282828", surface="#3c3836", surface2="#32302f",
        surface3="#45413d", surface4="#504945",
        primary="#b8bb26", text="#ebdbb2",
        subtext1="#d5c4a1", subtext2="#bdae93", subtext3="#7c6f64",
        separator="#3c3836", border="#504945", toast_bg="#242220",
    ),
    Theme(
        "tokyo-night", "Tokyo Night",
        bg="#1a1b26", surface="#24283b", surface2="#1f2335",
        surface3="#2d3149", surface4="#292e42",
        primary="#7aa2f7", text="#c0caf5",
        subtext1="#a9b1d6", subtext2="#737aa2", subtext3="#565f89",
        separator="#292e42", border="#414868", toast_bg="#16161e",
    ),
    Theme(
        "catppuccin", "Catppuccin",
        bg="#1e1e2e", surface="#313244", surface2="#24253a",
        surface3="#3d3f53", surface4="#45475a",
        primary="#cba6f7", text="#cdd6f4",
        subtext1="#bac2de", subtext2="#9399b2", subtext3="#6c7086",
        separator="#313244", border="#45475a", toast_bg="#181825",
    ),
    Theme(
        "solarized", "Solarized",
        bg="#002b36", surface="#073642", surface2="#00323f",
        surface3="#0a404e", surface4="#0d4a5a",
        primary="#268bd2", text="#eee8d5",
        subtext1="#93a1a1", subtext2="#839496", subtext3="#586e75",
        separator="#073642", border="#0d4a5a", toast_bg="#002030",
    ),
    Theme(
        "one-dark", "One Dark",
        bg="#282c34", surface="#2f333d", surface2="#2b2f38",
        surface3="#383d49", surface4="#3e4452",
        primary="#98c379", text="#abb2bf",
        subtext1="#9aa0aa", subtext2="#828997", subtext3="#5c6370",
        separator="#3e4452", border="#4b5263", toast_bg="#21252d",
    ),
    Theme(
        "monokai", "Monokai",
        bg="#272822", surface="#3e3d32", surface2="#2d2c28",
        surface3="#48483e", surface4="#49483e",
        primary="#a6e22e", text="#f8f8f2",
        subtext1="#cfcfc2", subtext2="#75715e", subtext3="#5c5a51",
        separator="#3e3d32", border="#49483e", toast_bg="#1e1e1a",
    ),
]

# ── Runtime state ──────────────────────────────────────────────────────────────

_current: Theme = THEMES[0]


def current() -> Theme:
    return _current


def primary() -> str:
    return _current.primary


def _set(theme: Theme) -> None:
    global _current
    _current = theme


# ── Persistence ───────────────────────────────────────────────────────────────

_CONFIG_DIR = Path.home() / ".config" / "spotty"
THEME_CSS_PATH = _CONFIG_DIR / "theme.tcss"
_CONFIG_PATH = _CONFIG_DIR / "config.json"


def load_saved() -> str:
    try:
        return json.loads(_CONFIG_PATH.read_text()).get("theme", "spotify")
    except Exception:
        return "spotify"


def save(name: str) -> None:
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps({"theme": name}))
    except Exception:
        pass


def get(name: str) -> Theme:
    return next((t for t in THEMES if t.name == name), THEMES[0])


# ── CSS generation ────────────────────────────────────────────────────────────

def generate_css(t: Theme) -> str:
    return f"""\
/* spotty theme: {t.label} */

Screen {{
    background: {t.bg};
}}

#np-loading {{
    color: {t.subtext2};
}}

#np-name {{
    color: {t.text};
}}

#np-artist {{
    color: {t.primary};
}}

#np-album {{
    color: {t.subtext2};
}}

#np-time {{
    color: {t.subtext2};
}}

#np-hints {{
    color: {t.subtext3};
}}

#modal-container, #search-container {{
    background: {t.surface};
}}

#search-title, #modal-title {{
    color: {t.primary};
}}

#search-hint, #modal-hint {{
    color: {t.subtext3};
}}

#search-input {{
    background: {t.surface3};
    color: {t.text};
}}

#search-input:focus {{
    background: {t.surface4};
}}

#search-results, #playlist-list, #home-list {{
    background: {t.surface2};
}}

#search-results > ListItem,
#playlist-list > ListItem,
#home-list > ListItem {{
    background: {t.bg};
    color: {t.subtext3};
}}

#search-results > ListItem:hover,
#playlist-list > ListItem:hover,
#home-list > ListItem:hover,
#search-results > ListItem.-highlight,
#playlist-list > ListItem.-highlight,
#home-list > ListItem.-highlight {{
    background: {t.surface4};
    color: {t.text};
    border-left: tall {t.primary};
}}

#artist-container {{
    background: {t.surface};
}}

#artist-stats {{
    color: {t.subtext2};
}}

#artist-sep {{
    color: {t.separator};
}}

#lyrics-container {{
    background: {t.surface};
}}

#lyrics-scroll {{
    background: {t.surface2};
}}

#lyrics-text {{
    color: {t.subtext1};
}}

Toast {{
    background: {t.toast_bg};
    border: round {t.border};
    color: {t.text};
}}

Toast.-information {{
    border: round {t.primary};
}}

Toast.-warning {{
    border: round #FFC107;
    color: #ffffff;
}}

Toast.-error {{
    border: round #E22134;
    color: #ffffff;
}}

.toast--title {{
    color: {t.text};
}}
"""


def write_css(theme: Theme | None = None) -> None:
    t = theme or _current
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        THEME_CSS_PATH.write_text(generate_css(t))
    except Exception:
        pass


def init() -> None:
    """Load saved theme preference and write CSS. Call before App init."""
    name = load_saved()
    theme = get(name)
    _set(theme)
    write_css(theme)
