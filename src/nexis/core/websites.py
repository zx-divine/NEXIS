"""Controlled website names and validated HTTP(S) destinations. No DNS guessing."""

import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

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
    "reddit": "https://www.reddit.com/",
}


def website_url(value):
    """Normalize a bare domain to HTTPS. HTTP requires an explicit scheme.

    Kept separate from the HTTPS-only validator for updates, providers and saved
    resources. Validation performs no network request and never executes text.
    """
    if (not isinstance(value, str) or not value or len(value) > 8192
            or any(c.isspace() or unicodedata.category(c).startswith("C") for c in value)
            or any(c in value for c in '\\"<>`')
            or re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", value, re.I)):
        raise ValueError("Enter an HTTP(S) address without whitespace, controls or credentials.")
    explicit = bool(re.match(r"https?://", value, re.I))
    if not explicit and (value.startswith(("/", "-")) or re.match(r"[a-z][a-z0-9+.-]*:(?!\d)", value, re.I)):
        raise ValueError("Only HTTP and HTTPS website addresses are supported.")
    try:
        parts = urlsplit(value if explicit else "https://" + value)
        host = parts.hostname
        port = parts.port  # Access validates malformed and out-of-range ports.
        if (parts.scheme.lower() not in {"http", "https"} or not host
                or parts.username is not None or parts.password is not None
                or parts.netloc.endswith(":")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
            host = "[" + str(address) + "]" if address.version == 6 else str(address)
        except ValueError:
            host = host.encode("idna").decode("ascii").lower()
            labels = host.rstrip(".").split(".")
            if (len(host) > 253 or len(labels) < 2 or labels[-1].isdigit()
                    or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)):
                raise ValueError()
        authority = host + (":" + str(port) if port is not None else "")
        return urlunsplit((parts.scheme.lower(), authority, parts.path, parts.query, parts.fragment))
    except (ValueError, UnicodeError):
        raise ValueError("Invalid website address. Use a full HTTP(S) URL or a valid bare domain; credentials are not allowed.") from None


def resolve_website(request):
    key = request.strip().casefold()
    if key in WEBSITES:
        return WEBSITES[key], False
    if key.startswith(("https://", "http://")) or "." in key or ":" in key:
        target = website_url(request.strip())
        # Only the exact controlled HTTPS destinations avoid unfamiliar-site review.
        known = target.rstrip("/") in {value.rstrip("/") for value in WEBSITES.values()}
        return target, not known
    if ":" in key or "/" in key or "." in key:
        raise ValueError(
            "Enter a valid bare domain or full HTTP(S) address. NEXIS never invents domains."
        )
    return None, False


def split_browser(argument):
    """Narrow suffix grammar; never extracts instructions from within a URL."""
    from nexis.platform.website_launcher import browser_name

    match = re.fullmatch(r"(.+?)\s+(?:in|using|with)\s+(.+)", argument.strip(), re.I)
    if not match:
        return argument.strip(), "default"
    site, browser = match.groups()
    return site.strip(), browser_name(browser.rstrip(".?!"))


def website_command(text):
    """Recognize a single website-open request without needing cloud inference.

    Compound commands remain in the normal planner. Unknown names do not become
    guessed domains. URLs keep their path/query punctuation intact.
    """
    match = re.fullmatch(r"(?:hey\s+)?(?:nexis[, :]\s*)?(?:please\s+)?open\s+(.+)", text.strip(), re.I)
    if not match:
        return None
    argument = match[1]
    site, browser = split_browser(argument)
    if re.search(r"\s+(?:and|then)\s+", site, re.I):
        return None
    if not any(c in site for c in "/:?"):
        site = site.rstrip(".!?")
    target, _ = resolve_website(site)
    if not target:
        return None
    return "open " + site + (" in " + browser if browser != "default" else "")
