"""Preserve interpreter-owned TLS policy resources in a frozen distribution.

Some managed Python builds load a public certificate-distrust sidecar from
beside ssl.py. Copy it unchanged; never patch SSLContext or disable verification.
Ordinary CPython builds require no extra file.
"""

from pathlib import Path
import ssl

SIDECAR = "codex-rejected-cas.pem"


def ssl_runtime_data(ssl_file=None):
    source = Path(ssl_file or ssl.__file__)
    resource = source.with_name(SIDECAR)
    text = source.read_text(encoding="utf-8") if source.is_file() else ""
    if not resource.is_file():
        if SIDECAR in text:
            raise RuntimeError("This interpreter requires its public TLS distrust resource. Restore the complete interpreter before building; TLS verification was not bypassed.")
        return []
    content = resource.read_bytes()
    if (not 1 <= len(content) <= 131072 or b"PRIVATE KEY" in content.upper()
            or not content.startswith(b"-----BEGIN TRUSTED CERTIFICATE-----")
            or b"-----END TRUSTED CERTIFICATE-----" not in content):
        raise RuntimeError("The interpreter TLS resource is invalid or contains private key material; packaging stopped.")
    return [(str(resource.resolve()), ".")]
