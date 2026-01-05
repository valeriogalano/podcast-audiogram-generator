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


class TestRssService(unittest.TestCase):
    def test_parse_feed_shapes_and_fields(self):
        episodes, podcast_info = rss_svc.parse_feed(SAMPLE_FEED)

        # Podcast-level info
        self.assertEqual(podcast_info.get('title'), 'My Podcast')
        self.assertEqual(podcast_info.get('image_url'), 'https://example.com/podcast.jpg')
        self.assertIn('AI', podcast_info.get('keywords'))

        # Episodes should be ordered oldest -> newest with numbering starting at 1
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


if __name__ == '__main__':
    unittest.main()
