import unittest
from audiogram_generator.services import rss as rss_svc

SAMPLE_FEED = (
    """
    <rss version="2.0"
         xmlns:podcast="https://podcastindex.org/namespace/1.0"
         xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
      <channel>
        <title>My Podcast</title>
        <item>
          <guid>guid-1</guid>
          <title>Episode 1</title>
          <podcast:soundbite startTime="10" duration="5">Feed Soundbite</podcast:soundbite>
        </item>
        <item>
          <guid>guid-2</guid>
          <title>Episode 2</title>
        </item>
      </channel>
    </rss>
    """
).strip()

class TestManualSoundbites(unittest.TestCase):
    def test_merge_manual_soundbites_by_guid(self):
        manual_sbs = {
            'guid-1': [
                {'start': '20', 'duration': '10', 'text': 'Manual Soundbite'}
            ]
        }
        episodes, _ = rss_svc.parse_feed(SAMPLE_FEED, manual_soundbites=manual_sbs)
        
        ep1 = next(ep for ep in episodes if ep['title'] == 'Episode 1')
        self.assertEqual(len(ep1['soundbites']), 2)
        self.assertEqual(ep1['soundbites'][0]['text'], 'Manual Soundbite')
        self.assertEqual(ep1['soundbites'][1]['text'], 'Feed Soundbite')

    def test_manual_soundbites_by_number(self):
        # We need to be careful with numbering. 
        # Episode 1 is first in XML -> last in reversed(entries) -> number 2
        # Episode 2 is second in XML -> first in reversed(entries) -> number 1
        manual_sbs = {
            2: [{'start': '30', 'duration': '5', 'text': 'By Number Int'}],
            '1': [{'start': '40', 'duration': '5', 'text': 'By Number Str'}]
        }
        episodes, _ = rss_svc.parse_feed(SAMPLE_FEED, manual_soundbites=manual_sbs)
        
        ep1 = next(ep for ep in episodes if ep['title'] == 'Episode 1')
        self.assertEqual(ep1['soundbites'][0]['text'], 'By Number Int')
        
        ep2 = next(ep for ep in episodes if ep['title'] == 'Episode 2')
        self.assertEqual(ep2['soundbites'][0]['text'], 'By Number Str')

    def test_manual_soundbites_precedence_over_feed(self):
        manual_sbs = {
            'guid-1': [{'start': '0', 'duration': '10', 'text': 'Manual'}]
        }
        episodes, _ = rss_svc.parse_feed(SAMPLE_FEED, manual_soundbites=manual_sbs)
        ep1 = next(ep for ep in episodes if ep['title'] == 'Episode 1')
        self.assertEqual(ep1['soundbites'][0]['text'], 'Manual')
        self.assertEqual(ep1['soundbites'][1]['text'], 'Feed Soundbite')

if __name__ == '__main__':
    unittest.main()
