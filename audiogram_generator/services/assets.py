"""Asset-related services (e.g., image downloads).

Network I/O is isolated here to keep the CLI/test flows clean and mockable.
"""
from __future__ import annotations

import logging
import urllib.request

from .errors import AssetDownloadError
from ._http import make_ssl_context


logger = logging.getLogger(__name__)


def download_image(url: str, output_path: str, timeout: int = 10, verify_ssl: bool = False) -> str:
    """Download an image from ``url`` into ``output_path``.

    Returns the ``output_path`` on success. Raises exceptions on failure.
    """
    logger.info("Downloading image: %s -> %s", url, output_path)

    ssl_context = make_ssl_context(verify=verify_ssl)

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, context=ssl_context, timeout=timeout) as response:
            data = response.read()
            with open(output_path, "wb") as f:
                f.write(data)
        logger.debug("Image saved to %s (%d bytes)", output_path, len(data))
        return output_path
    except Exception as e:
        logger.error("Failed to download image from %s: %s", url, e)
        raise AssetDownloadError(str(e))
