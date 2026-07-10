"""
app/utils/helpers.py
─────────────────────
Shared utility functions used across the codebase.
"""
from __future__ import annotations

import re
from typing import Optional


def parse_inr(value: str) -> Optional[float]:
    """
    Parse an INR price string to float.
    Handles: "₹2,999", "Rs. 2999", "2999.00", "3k", "1.5 lakh"
    """
    if not value:
        return None
    v = value.lower().strip()
    v = re.sub(r"[₹rs.,\s]", "", v)

    # Handle shorthand
    multiplier = 1.0
    if v.endswith("k"):
        multiplier = 1_000
        v = v[:-1]
    elif v.endswith("lakh") or v.endswith("l"):
        multiplier = 100_000
        v = v.rstrip("lakh").rstrip("l")

    try:
        return float(v) * multiplier
    except ValueError:
        return None


def truncate(text: str, max_chars: int = 200) -> str:
    """Truncate text to max_chars, appending '…' if cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def platform_display_name(platform: str) -> str:
    """Human-readable platform name."""
    names = {
        "amazon": "Amazon India",
        "flipkart": "Flipkart",
        "myntra": "Myntra",
        "ajio": "Ajio",
        "nykaa": "Nykaa",
        "blinkit": "Blinkit",
        "zepto": "Zepto",
        "instamart": "Swiggy Instamart",
        "zomato": "Zomato",
        "serp": "Google Shopping",
    }
    return names.get(platform.lower(), platform.title())
