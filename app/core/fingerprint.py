import hashlib
import re
from typing import Optional

LEGAL_SUFFIXES = {
    "pvt",
    "ltd",
    "private",
    "limited",
    "inc",
    "incorporated",
    "llp",
    "llc",
    "corp",
    "corporation",
    "co",
    "technologies",
    "technology",
}


def normalize_text(text: Optional[str]) -> str:
    """
    Lowercases, strips punctuation, removes common legal suffixes,
    and collapses whitespace.
    """
    if not text:
        return ""
    # Lowercase
    s = str(text).lower()
    # Strip punctuation and underscore (replace with space)
    s = re.sub(r"[^\w\s]|_", " ", s)
    words = s.split()
    filtered = [w for w in words if w not in LEGAL_SUFFIXES]
    if not filtered:
        filtered = words
    return " ".join(filtered)


def canonical_location_key(location: Optional[str]) -> str:
    """
    Maps arbitrary location string to a canonical city key:
    (e.g., hyderabad, bengaluru, pune, mumbai), or remote-india, remote, unknown.
    """
    if not location:
        return "unknown"
    loc = str(location).lower().strip()
    if not loc or loc in ("unknown", "unspecified", "none", "null"):
        return "unknown"

    # Exact or substring match for major Indian tech hubs
    # South
    if any(c in loc for c in ["bengaluru", "bangalore"]):
        return "bengaluru"
    if any(c in loc for c in ["hyderabad", "secunderabad", "cyberabad"]):
        return "hyderabad"
    if any(c in loc for c in ["chennai", "madras"]):
        return "chennai"
    if any(c in loc for c in ["kochi", "cochin", "calicut", "kozhikode", "trivandrum", "thiruvananthapuram"]):
        return "kochi"
    for city in ["coimbatore", "mysore", "mysuru", "mangalore", "mangaluru", "visakhapatnam", "vizag", "vijayawada"]:
        if city in loc:
            return city

    # West & Central
    if any(c in loc for c in ["mumbai", "navi mumbai", "thane"]):
        return "mumbai"
    if "pune" in loc:
        return "pune"
    if any(c in loc for c in ["ahmedabad", "gandhinagar", "surat", "vadodara", "baroda"]):
        return "ahmedabad"
    for city in ["indore", "bhopal", "nagpur", "nashik", "goa"]:
        if city in loc:
            return city

    # North
    if any(c in loc for c in ["delhi", "new delhi"]):
        return "delhi"
    if any(c in loc for c in ["gurgaon", "gurugram"]):
        return "gurugram"
    if any(c in loc for c in ["noida", "greater noida"]):
        return "noida"
    if any(c in loc for c in ["chandigarh", "mohali", "panchkula"]):
        return "chandigarh"
    for city in ["jaipur", "lucknow", "kanpur", "dehradun"]:
        if city in loc:
            return city

    # East & North East
    if any(c in loc for c in ["kolkata", "calcutta"]):
        return "kolkata"
    for city in ["bhubaneswar", "patna", "ranchi", "guwahati"]:
        if city in loc:
            return city

    # Remote vs Regional
    is_remote = any(r in loc for r in ["remote", "anywhere", "telecommute", "wfh", "work from home"])
    is_india = "india" in loc or "in" in loc.split()

    if is_remote and is_india:
        return "remote-india"
    if is_remote:
        return "remote"
    if is_india:
        return "remote-india"

    return "unknown"


def compute_fingerprint(company: Optional[str], title: Optional[str], location: Optional[str]) -> str:
    """
    Computes a deterministic SHA1 fingerprint:
    sha1(normalize(company) + "|" + normalize(title) + "|" + normalize(location_key))
    """
    c = normalize_text(company or "")
    t = normalize_text(title or "")
    loc_key = canonical_location_key(location or "")
    raw = f"{c}|{t}|{loc_key}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
