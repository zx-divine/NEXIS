"""Curated destinations; unknown requests must be explicit HTTPS addresses."""

from nexis.utils.validation import url

WEBSITES = {
    "youtube": "https://www.youtube.com/",
    "github": "https://github.com/",
    "wikipedia": "https://www.wikipedia.org/",
    "google": "https://www.google.com/",
    "chatgpt": "https://chatgpt.com/",
    "gmail": "https://mail.google.com/",
    "outlook": "https://outlook.live.com/",
    "bing": "https://www.bing.com/",
    "stackoverflow": "https://stackoverflow.com/",
}


def resolve_website(request):
    key = request.strip().casefold()
    if key in WEBSITES:
        return WEBSITES[key], False
    if key.startswith("https://"):
        return url(request.strip()), True
    if ":" in key or "/" in key or "." in key:
        raise ValueError(
            "For an unfamiliar website, enter its full HTTPS address. NEXIS will ask before opening it."
        )
    return None, False
