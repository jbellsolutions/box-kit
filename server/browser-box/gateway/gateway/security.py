"""URL target-scope classification and input validation.

Ported from Super Browser's `src/super_browser/security.py`, which is the only part of
that codebase worth carrying forward verbatim: it is the control that stops a browser
sitting on your own VPS from being talked into reading your other services.

The obfuscated-IPv4 handling is the part people get wrong. Browsers accept 0x7f000001,
2130706433, 0177.0.0.1 and 127.1 as loopback; `ipaddress.ip_address` rejects all four,
so a naive check falls through to "public web" and happily fetches localhost.
"""
from __future__ import annotations

import socket
from ipaddress import ip_address, ip_network
from typing import Literal
from urllib.parse import urlparse

TargetScope = Literal["none", "public_web", "loopback", "private_network", "link_local", "local_file"]

ALLOWED_URL_SCHEMES = ("http", "https")
LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}
# Carrier-grade NAT. Python's ipaddress calls it neither private nor global, so it slipped
# through as "public" — and it is Tailscale's address space, i.e. a tailnet's private hosts.
SHARED_ADDRESS_SPACE = ip_network("100.64.0.0/10")
PRIVATE_HOST_SUFFIXES = (".local", ".internal", ".lan", ".home", ".corp")


class UnsafeUrl(ValueError):
    """The URL is syntactically valid but must not be opened by a browser on this host."""


def validate_url(url: str | None) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    value = url.strip()
    if any(char.isspace() for char in value):
        raise ValueError("url must not contain whitespace; percent-encode spaces as %20")
    parsed = urlparse(value)
    if not parsed.scheme:
        raise ValueError("url must include a scheme, such as https://")
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise ValueError("url must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("url must not carry credentials; use a session instead")
    if not parsed.netloc:
        raise ValueError("url must include a host")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("url port must be a valid integer") from exc
    return value


def _canonical_ipv4(host: str) -> str | None:
    """Normalize octal/hex/decimal/short-dotted IPv4 (0x7f000001, 127.1, 2130706433)."""
    try:
        return socket.inet_ntoa(socket.inet_aton(host))
    except OSError:
        return None


def target_scope(url: str | None) -> TargetScope:
    """Classify where a URL points. Never raises; an unparseable URL is 'none'."""
    if not url:
        return "none"
    parsed = urlparse(url)
    if parsed.scheme.lower() == "file":
        return "local_file"
    if parsed.scheme.lower() not in ("http", "https"):
        return "none"
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return "none"
    # Chromium resolves every *.localhost name to loopback itself, whatever DNS says.
    if host in LOCAL_HOSTNAMES or host.endswith(".localhost"):
        return "loopback"
    try:
        address = ip_address(host)
    except ValueError:
        canonical = _canonical_ipv4(host)
        if canonical is not None:
            address = ip_address(canonical)
        elif host.endswith(PRIVATE_HOST_SUFFIXES) or "." not in host:
            # A bare hostname with no dot resolves through internal DNS, not the public web.
            return "private_network"
        else:
            return "public_web"
    # ::ffff:127.0.0.1 is 127.0.0.1. Judge the IPv4 it carries; Python versions disagree on
    # what an IPv4-mapped address "is", and the gateway must not depend on which one it runs.
    if address.version == 6 and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link_local"
    if address.is_private or address.is_unspecified or address.is_reserved or (
        address.version == 4 and address in SHARED_ADDRESS_SPACE
    ):
        return "private_network"
    return "public_web"


def require_public_web(url: str) -> str:
    """Validate and refuse anything that is not the public internet. Raises UnsafeUrl.

    This is a check on the URL as written. A hostname that RESOLVES inward still passes
    here — see require_public_addresses, which every caller must also run.
    """
    value = validate_url(url)
    scope = target_scope(value)
    if scope != "public_web":
        raise UnsafeUrl(
            f"refused: {value} resolves to {scope}, and this browser only opens the public web. "
            "Loopback, private, link-local and file targets are blocked so a page cannot be used "
            "to read services running beside it."
        )
    return value


def require_public_addresses(host: str | None) -> list[str]:
    """Resolve a hostname and refuse if ANY address it answers with points inward.

    Scope-by-name is not enough: evil.example is a perfectly ordinary public name that can
    A-record to 10.0.0.5. This closes that. It does NOT close DNS rebinding — the answer can
    change between this check and the connection — which is why the network-level egress
    rule in the README is the real control and this is defence in depth.

    Blocking; call it with asyncio.to_thread.
    """
    if not host:
        raise UnsafeUrl("refused: no host to resolve")
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrl(f"refused: {host} does not resolve ({exc})") from None
    addresses = sorted({info[4][0].split("%")[0] for info in infos})
    if not addresses:
        raise UnsafeUrl(f"refused: {host} resolved to nothing")
    for address in addresses:
        scope = target_scope(f"http://[{address}]" if ":" in address else f"http://{address}")
        if scope != "public_web":
            raise UnsafeUrl(
                f"refused: {host} resolves to {address}, which is {scope}. A public hostname "
                "pointing at a private address is how a page gets a browser to read the services "
                "running beside it."
            )
    return addresses
