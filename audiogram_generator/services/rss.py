"""RSS fetching and parsing services for podcast episodes and metadata.

Split into network I/O (fetch_feed) and pure parsing (parse_feed) so tests can
run offline by providing XML strings. The parsing mirrors the legacy
implementation in ``cli.get_podcast_episodes`` to preserve behavior.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import logging

import feedparser  # type: ignore
from .errors import RssError

logger = logging.getLogger(__name__)


def fetch_feed(url: str, timeout: int = 10) -> str:
    """Fetch RSS/Atom feed XML from a URL with a relaxed SSL context.

    Returns the decoded UTF-8 text. Raises exceptions on network errors.
    """
    logger.info("Fetching RSS feed: %s", url)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, context=ssl_context, timeout=timeout) as response:
            xml = response.read().decode("utf-8")
            logger.debug("Fetched %d bytes of feed XML", len(xml))
            return xml
    except Exception as e:
        logger.error("Failed to fetch RSS feed from %s: %s", url, e)
        raise RssError(str(e))


def parse_feed(feed_xml: str, manual_soundbites: dict = None) -> Tuple[List[Dict], Dict]:
    """Parse the feed XML and return (episodes, podcast_info).

    The output shape matches the legacy CLI implementation:
    - podcast_info keys: ``title``, ``image_url`` (optional), ``keywords`` (optional)
    - episodes: list of dicts ordered oldest->newest, each contains:
      ``number``, ``title``, ``link``, ``description``, ``soundbites`` (list),
      ``transcript_url`` (optional), ``audio_url`` (optional), ``keywords`` (optional),
      ``image_url`` (optional)
    """
    root = ET.fromstring(feed_xml)

    # Namespaces used in the feed (Podcasting 2.0, iTunes, Media RSS)
    namespaces = {
        'podcast': 'https://podcastindex.org/namespace/1.0',
        'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'media': 'http://search.yahoo.com/mrss/',
    }

    # Podcast-level info
    podcast_info: Dict = {}
    channel = root.find('.//channel')
    if channel is not None:
        title_elem = channel.find('title')
        if title_elem is not None and title_elem.text:
            podcast_info['title'] = title_elem.text.strip()

        image_elem = channel.find('image')
        if image_elem is not None:
            url_elem = image_elem.find('url')
            if url_elem is not None and url_elem.text:
                podcast_info['image_url'] = url_elem.text.strip()
        if not podcast_info.get('image_url'):
            ch_itunes_img = channel.find('itunes:image', namespaces)
            if ch_itunes_img is not None:
                href = ch_itunes_img.get('href') or ch_itunes_img.get('url')
                if href:
                    podcast_info['image_url'] = href.strip()

        keywords_elem = channel.find('itunes:keywords', namespaces)
        if keywords_elem is not None and keywords_elem.text:
            podcast_info['keywords'] = keywords_elem.text.strip()

    # Item-level extractions that require namespaces
    soundbites_by_guid: Dict[str, List[Dict]] = {}
    transcript_by_guid: Dict[str, str] = {}
    audio_by_guid: Dict[str, str] = {}
    keywords_by_guid: Dict[str, str] = {}
    episode_image_by_guid: Dict[str, str] = {}

    for item in root.findall('.//item'):
        guid_elem = item.find('guid')
        guid = guid_elem.text.strip() if (guid_elem is not None and guid_elem.text) else ''

        # podcast:soundbite entries
        soundbites: List[Dict] = []
        for sb in item.findall('podcast:soundbite', namespaces):
            soundbites.append({
                'start': sb.get('startTime'),
                'duration': sb.get('duration'),
                'text': sb.text.strip() if sb.text else 'No description',
            })
        if soundbites:
            soundbites_by_guid[guid] = soundbites

        # podcast:transcript url
        transcript_elem = item.find('podcast:transcript', namespaces)
        if transcript_elem is not None:
            transcript_url = transcript_elem.get('url')
            if transcript_url:
                transcript_by_guid[guid] = transcript_url

        # enclosure audio
        enclosure_elem = item.find('enclosure')
        if enclosure_elem is not None:
            audio_url = enclosure_elem.get('url')
            if audio_url:
                audio_by_guid[guid] = audio_url

        # itunes:keywords at item level
        it_kw = item.find('itunes:keywords', namespaces)
        if it_kw is not None and it_kw.text:
            keywords_by_guid[guid] = it_kw.text.strip()

        # Episode-specific image (prefer itunes:image, then media:thumbnail/content)
        ep_img_url = None
        itunes_img = item.find('itunes:image', namespaces)
        if itunes_img is not None:
            ep_img_url = itunes_img.get('href') or itunes_img.get('url')
        if not ep_img_url:
            media_thumb = item.find('media:thumbnail', namespaces)
            if media_thumb is not None:
                ep_img_url = media_thumb.get('url')
        if not ep_img_url:
            media_content = item.find('media:content', namespaces)
            if media_content is not None:
                ep_img_url = media_content.get('url')
        if ep_img_url:
            episode_image_by_guid[guid] = ep_img_url.strip()

    # Use feedparser to iterate entries and create episode list (mirrors legacy)
    feed = feedparser.parse(feed_xml)

    episodes: List[Dict] = []
    total_episodes = len(feed.entries)

    for idx, entry in enumerate(reversed(feed.entries)):
        episode_number = idx + 1  # oldest to newest numbering
        guid = entry.get('guid', entry.get('id', ''))
        
        # Retrieve soundbites from feed
        feed_sbs = soundbites_by_guid.get(guid, [])
        
        # Retrieve manual soundbites (by GUID or episode number)
        manual_sbs = []
        if manual_soundbites:
            manual_sbs = manual_soundbites.get(guid) or manual_soundbites.get(episode_number) or manual_soundbites.get(str(episode_number)) or []
        
        # Merge soundbites
        all_sbs = manual_sbs + feed_sbs
        
        episode = {
            'number': episode_number,
            'title': entry.get('title', 'No title'),
            'link': entry.get('link', ''),
            'description': entry.get('description', ''),
            'soundbites': all_sbs,
            'transcript_url': transcript_by_guid.get(guid, None),
            'audio_url': audio_by_guid.get(guid, None),
            'keywords': keywords_by_guid.get(guid, None),
            'image_url': episode_image_by_guid.get(guid, None),
        }
        episodes.append(episode)

    return episodes, podcast_info


def get_podcast_episodes(feed_url: str, manual_soundbites: dict = None) -> Tuple[List[Dict], Dict]:
    """High-level convenience that fetches and parses the feed URL.

    Network I/O is isolated to ``fetch_feed`` to allow tests to mock it.
    """
    xml_text = fetch_feed(feed_url)
    return parse_feed(xml_text, manual_soundbites=manual_soundbites)
