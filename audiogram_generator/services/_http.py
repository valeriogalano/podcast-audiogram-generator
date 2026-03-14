"""Shared HTTP utilities for service modules."""
from __future__ import annotations

import ssl


def make_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Return an SSL context with verification enabled or disabled.

    When *verify* is False the context skips certificate and hostname checks.
    Callers are responsible for logging a warning when this is the case.
    """
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx
