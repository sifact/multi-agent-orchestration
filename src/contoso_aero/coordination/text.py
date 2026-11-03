"""Replace look-alike characters that models emit with the plain ones the data uses.

Models sometimes write a non-breaking hyphen inside an identifier (CX7-10041), a narrow
no-break space, or full-width brackets. They look identical on screen but do not match the
database, exact-match scoring or what a person copies back into the next question, so every
model-written string is cleaned before it is passed on or shown.
"""

from __future__ import annotations

_PLAIN = str.maketrans({
    "\u00a0": " ", "\u2007": " ", "\u2009": " ", "\u200a": " ", "\u202f": " ",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2212": "-",
    "\u200b": None, "\u2060": None, "\ufeff": None,
    "\u3010": "[", "\u3011": "]",
})


def clean_model_text(text: str) -> str:
    """Return `text` with look-alike spaces, hyphens, brackets and invisible characters made plain."""
    return text.translate(_PLAIN)
