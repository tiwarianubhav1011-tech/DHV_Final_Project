#!/usr/bin/env python3
"""
Text and city normalization utilities for cross-year NIRF institute unification.
"""

import re
from difflib import SequenceMatcher
import pandas as pd

from config import (
    ABBREVIATIONS,
    CAMPUS_CODES,
    CITY_ALIASES,
    NOISE_PATTERNS,
    GENERIC_PREFIXES,
)


def norm_city(city) -> str:
    """Normalize a city string to lowercase canonical spelling."""
    s = str(city).lower().strip() if pd.notna(city) else ""
    s = re.sub(r",.*$", "", s)                 # "Gurugram, Haryana" → "gurugram"
    s = re.sub(r"\(.*?\)", "", s)              # "Prayagraj (Allahabad)"
    s = re.sub(r"[-\s]*\d+$", "", s)           # "Calcutta-16"
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return CITY_ALIASES.get(s, s)


def norm_name(name) -> str:
    """Normalize an institution name by expanding abbreviations and stripping noise."""
    s = str(name).lower()
    s = s.replace("`", "'").replace("’", "'")
    # "IIT B" / "IIT-Bombay" / "IIT KGP"
    m = re.match(r"^\s*iit[\s\-,]+([a-z]+)\s*$", s)
    if m and m.group(1) in CAMPUS_CODES:
        s = f"iit {CAMPUS_CODES[m.group(1)]}"
    for pat, rep in ABBREVIATIONS.items():
        s = re.sub(pat, rep, s)
    s = s.replace("&", " and ")
    s = re.sub(r"'s\b", "s", s).replace("'", "")
    s = re.sub(r"\bst\.?\s", "st ", s)
    s = re.sub(r"\bdr\.?\s", "dr ", s)
    s = re.sub(r"\bgovt\.?\b|\bgovernment\b", "govt", s)
    s = re.sub(r"\bunversity\b", "university", s)       # typo in source
    for pat in NOISE_PATTERNS:
        s = re.sub(pat, " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\b([a-z])\s(?=[a-z]\b)", r"\1", s)     # "n g p" → "ngp", "s r m" → "srm"
    return re.sub(r"\s+", " ", s).strip()


def strip_city(nname: str, ncity: str, raw_city: str) -> str:
    """
    Drop a trailing/embedded city from the name, but never reduce a name to a
    bare system prefix like 'indian institute of technology'.
    """
    out = nname
    for c in {ncity, norm_city(raw_city), re.sub(r"[^a-z\s]", " ", str(raw_city).lower()).strip()}:
        if c and out.endswith(" " + c):
            out = out[: -len(c)].strip()
    if out in GENERIC_PREFIXES or len(out.split()) < 2:
        return nname
    return out


def sim(a: str, b: str) -> float:
    """Compute SequenceMatcher similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()

