import unittest
from unittest.mock import patch

from audiogram_generator.services import rss as rss_svc


SAMPLE_FEED = (
    """
    <rss version="2.0"
         xmlns:podcast="https://podcastindex.org/namespace/1.0"
         xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
         xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <title>My Podcast</title>
        <image><url>https://example.com/podcast.jpg</url></image>
        <itunes:keywords>AI, Coding</itunes:keywords>

        <!-- Newest item first (common in feeds) -->
        <item>
          <guid>g2</guid>
          <title>Episode B</title>
          <link>https://example.com/ep-b</link>
          <description>Desc B</description>
          <enclosure url="https://example.com/ep-b.mp3" type="audio/mpeg" />
          <itunes:keywords>Dev Ops</itunes:keywords>
          <itunes:image href="https://example.com/ep-b.jpg" />
          <podcast:transcript url="https://example.com/ep-b.srt" type="application/srt" />
          <podcast:soundbite startTime="5" duration="4">Segment B</podcast:soundbite>
        </item>

        <item>
          <guid>g1</guid>
          <title>Episode A</title>
          <link>https://example.com/ep-a</link>
          <description>Desc A</description>
          <enclosure url="https://example.com/ep-a.mp3" type="audio/mpeg" />
          <itunes:keywords>Python</itunes:keywords>
          <media:thumbnail url="https://example.com/ep-a-thumb.jpg" />
          <podcast:transcript url="https://example.com/ep-a.srt" type="application/srt" />
          <podcast:soundbite startTime="10" duration="3">Segment A</podcast:soundbite>
        </item>
      </channel>
    </rss>
    """
).strip()


def _item(guid, title, episode=None):
    """Build a minimal <item>, optionally carrying an itunes:episode tag."""
    ep_tag = f"<itunes:episode>{episode}</itunes:episode>" if episode is not None else ""
    return (
        f"<item>"
        f"<guid>{guid}</guid>"
        f"<title>{title}</title>"
        f"<enclosure url=\"https://example.com/{guid}.mp3\" type=\"audio/mpeg\" />"
        f"{ep_tag}"
        f"</item>"
    )


def _feed(items):
    """Wrap item XML strings in a channel. Items are newest-first, as in real feeds."""
    return (
        "<rss version=\"2.0\""
        " xmlns:podcast=\"https://podcastindex.org/namespace/1.0\""
        " xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\""
        " xmlns:media=\"http://search.yahoo.com/mrss/\">"
        "<channel><title>My Podcast</title>"
        + "".join(items)
        + "</channel></rss>"
    )


class TestRssService(unittest.TestCase):
    def test_parse_feed_shapes_and_fields(self):
        episodes, podcast_info = rss_svc.parse_feed(SAMPLE_FEED)

        # Podcast-level info
        self.assertEqual(podcast_info.get('title'), 'My Podcast')
        self.assertEqual(podcast_info.get('image_url'), 'https://example.com/podcast.jpg')
        self.assertIn('AI', podcast_info.get('keywords'))

        # SAMPLE_FEED has no itunes:episode tags, so numbering falls back to the
        # feed position: oldest -> newest starting at 1.
        self.assertEqual(len(episodes), 2)
        self.assertEqual(episodes[0]['number'], 1)
        self.assertEqual(episodes[1]['number'], 2)

        # Oldest is Episode A (guid g1)
        ep_a = episodes[0]
        self.assertEqual(ep_a['title'], 'Episode A')
        self.assertEqual(ep_a['link'], 'https://example.com/ep-a')
        self.assertEqual(ep_a['description'], 'Desc A')
        self.assertEqual(ep_a['audio_url'], 'https://example.com/ep-a.mp3')
        self.assertEqual(ep_a['transcript_url'], 'https://example.com/ep-a.srt')
        self.assertEqual(ep_a['image_url'], 'https://example.com/ep-a-thumb.jpg')
        self.assertEqual(len(ep_a['soundbites']), 1)
        self.assertEqual(ep_a['soundbites'][0]['start'], '10')
        self.assertEqual(ep_a['soundbites'][0]['duration'], '3')
        self.assertIn('Segment A', ep_a['soundbites'][0]['text'])

        # Newest is Episode B (guid g2)
        ep_b = episodes[1]
        self.assertEqual(ep_b['title'], 'Episode B')
        self.assertEqual(ep_b['audio_url'], 'https://example.com/ep-b.mp3')
        self.assertEqual(ep_b['transcript_url'], 'https://example.com/ep-b.srt')
        self.assertEqual(ep_b['image_url'], 'https://example.com/ep-b.jpg')
        self.assertEqual(len(ep_b['soundbites']), 1)

    @patch('audiogram_generator.services.rss.fetch_feed')
    def test_get_podcast_episodes_uses_fetch_and_parse(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_FEED
        episodes, podcast_info = rss_svc.get_podcast_episodes('https://feed.example/rss.xml')
        self.assertEqual(len(episodes), 2)
        self.assertEqual(podcast_info.get('title'), 'My Podcast')
        mock_fetch.assert_called_once()

    def test_itunes_episode_used_as_identity(self):
        # itunes:episode drives the number even when it does not match the
        # 1-based feed position (here only two items but numbered 149/150).
        feed = _feed([
            _item('g150', 'Episode 150', episode=150),
            _item('g149', 'Episode 149', episode=149),
        ])
        episodes, _ = rss_svc.parse_feed(feed)

        by_title = {e['title']: e for e in episodes}
        self.assertEqual(by_title['Episode 149']['number'], 149)
        self.assertEqual(by_title['Episode 150']['number'], 150)

    def test_extra_untagged_item_does_not_shift_episode_identity(self):
        # A trailer/bonus item without itunes:episode enters the feed. The tagged
        # episodes must keep their identity (ep150 stays 150, not a shifted
        # position), while the untagged trailer falls back to its feed position.
        feed = _feed([
            _item('g150', 'Episode 150', episode=150),
            _item('g149', 'Episode 149', episode=149),
            _item('g148', 'Episode 148', episode=148),
            _item('gtrailer', 'Season Trailer'),  # oldest, no itunes:episode
        ])
        episodes, _ = rss_svc.parse_feed(feed)

        by_title = {e['title']: e for e in episodes}
        self.assertEqual(by_title['Episode 148']['number'], 148)
        self.assertEqual(by_title['Episode 149']['number'], 149)
        self.assertEqual(by_title['Episode 150']['number'], 150)
        # Trailer is the oldest position (idx 0) -> fallback number 1.
        self.assertEqual(by_title['Season Trailer']['number'], 1)

    def test_non_numeric_itunes_episode_falls_back_to_position(self):
        # A malformed itunes:episode must not crash; it falls back to position.
        feed = _feed([
            _item('g2', 'Episode B', episode=2),
            _item('gbonus', 'Bonus', episode='bonus'),  # non-numeric
        ])
        episodes, _ = rss_svc.parse_feed(feed)

        by_title = {e['title']: e for e in episodes}
        # Bonus is oldest (idx 0) -> fallback number 1; Episode B keeps 2.
        self.assertEqual(by_title['Bonus']['number'], 1)
        self.assertEqual(by_title['Episode B']['number'], 2)


if __name__ == '__main__':
    unittest.main()
