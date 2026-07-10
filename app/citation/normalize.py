"""Title normalization for cross-provider bibliographic comparison.

Comparison pipeline (per plan): HTML unescape -> LaTeX normalization ->
Unicode NFKC -> casefold -> whitespace collapse. Normalization is only ever
used to *compare* titles; the original strings and their provenance are kept
by the caller. An empty normalized title never matches anything.
"""

from __future__ import annotations

import html
import re
import unicodedata

# LaTeX accent commands -> combining characters (applied to the next letter).
_LATEX_ACCENTS = {
    "`": "̀",  # grave
    "'": "́",  # acute
    "^": "̂",  # circumflex
    "~": "̃",  # tilde
    '"': "̈",  # umlaut
    "=": "̄",  # macron
    ".": "̇",  # dot above
    "u": "̆",  # breve
    "v": "̌",  # caron
    "H": "̋",  # double acute
    "c": "̧",  # cedilla
    "k": "̨",  # ogonek
    "r": "̊",  # ring
    "b": "̱",  # bar under
    "d": "̣",  # dot under
}

# LaTeX named glyph macros -> literal characters.
_LATEX_GLYPHS = {
    "ss": "ß", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ",
    "aa": "å", "AA": "Å", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł",
    "i": "ı", "j": "ȷ",
}

_ACCENT_RE = re.compile(
    r"\\([`'^\"~=.uvHckrbd])\s*\{?([A-Za-z])\}?"
)
_GLYPH_RE = re.compile(
    r"\\(" + "|".join(sorted(_LATEX_GLYPHS, key=len, reverse=True)) + r")\b\{?\}?"
)
# Word-like commands (\emph, \textit, \mathrm, ...): drop the command name,
# keep its argument (braces are stripped separately).
_COMMAND_RE = re.compile(r"\\[A-Za-z]+\s*")
_ESCAPED_CHAR_RE = re.compile(r"\\([%&$#_{}])")
_WS_RE = re.compile(r"\s+")


def strip_latex(text: str) -> str:
    """Flatten common LaTeX markup to plain text (accents, glyphs, braces)."""
    out = _ACCENT_RE.sub(lambda m: m.group(2) + _LATEX_ACCENTS[m.group(1)], text)
    out = _GLYPH_RE.sub(lambda m: _LATEX_GLYPHS[m.group(1)], out)
    out = _ESCAPED_CHAR_RE.sub(r"\1", out)
    out = out.replace("~", " ")  # LaTeX non-breaking space
    out = _COMMAND_RE.sub("", out)
    out = out.replace("{", "").replace("}", "").replace("$", "")
    return unicodedata.normalize("NFC", out)


def normalize_title(raw: str | None) -> str:
    """Normalize a title for equality comparison; '' means 'not comparable'."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = strip_latex(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    # Fold punctuation runs into single spaces so hyphenation/quote style
    # differences between providers do not break equality.
    text = "".join(
        ch if (ch.isalnum() or ch.isspace()) else " " for ch in text
    )
    return _WS_RE.sub(" ", text).strip()


def titles_match(a: str | None, b: str | None) -> bool:
    """True when both titles normalize to the same non-empty string.

    An empty normalized title never matches — a record with no comparable
    title cannot be confirmed equal to anything.
    """
    na = normalize_title(a)
    nb = normalize_title(b)
    return bool(na) and na == nb
