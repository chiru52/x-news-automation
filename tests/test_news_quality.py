"""Strict, offline matching for overlapping syndicated headlines."""
import unittest
from newsbot.news_quality import canonical_story_url, same_story, unique_stories


def article(title, url):
    return {"title": title, "source_url": url}


class NewsQualityTests(unittest.TestCase):
    def test_deduplicates_tracking_variants_without_erasing_real_query_parameters(self):
        a = article("OpenAI launches new AI tool", "https://example.com/story?utm_source=rss&edition=1")
        b = article("A different headline", "https://example.com/story?edition=1&fbclid=123")
        # URL canonicalization retains meaningful query parameters.
        self.assertEqual(canonical_story_url(a["source_url"]),
                         canonical_story_url(b["source_url"]))
        self.assertTrue(same_story(a, b))
        c = article("A different headline", "https://example.com/story?edition=2")
        self.assertFalse(same_story(a, c))

    def test_similar_syndicated_long_headlines_are_one_story(self):
        first = article("OpenAI launches enterprise AI coding assistant for developers today",
                        "https://publisher-one.example/story")
        repeated = article("OpenAI launches enterprise AI coding assistant for developers",
                           "https://publisher-two.example/news")
        self.assertTrue(same_story(first, repeated))
        self.assertEqual(unique_stories([first, repeated]), [first])

    def test_preserve_distinct_numbers_and_companies(self):
        old = article("Nvidia shares rise 12% after its earnings report",
                      "https://one.example/earnings")
        new = article("Nvidia shares rise 15% after its earnings report",
                      "https://two.example/earnings")
        self.assertFalse(same_story(old, new))
        nvidia = article("Nvidia releases advanced AI software for enterprise customers today",
                         "https://one.example/software")
        microsoft = article("Microsoft releases advanced AI software for enterprise customers today",
                            "https://two.example/software")
        self.assertFalse(same_story(nvidia, microsoft))

    def test_short_generic_headlines_do_not_cluster(self):
        a = article("Stocks rally today", "https://a.example/stock")
        b = article("Stocks rally today", "https://b.example/stock")
        self.assertFalse(same_story(a, b))
        self.assertEqual(len(unique_stories([a, b])), 2)

    def test_source_url_match_always_wins(self):
        one = article("New AI tool released", "https://example.org/story/")
        two = article("Revised headline about a different number", "https://example.org/story")
        self.assertTrue(same_story(one, two))

    def test_no_unsafe_url_is_accepted_as_same_url(self):
        a = article("A", "javascript:alert(1)")
        b = article("B", "javascript:alert(1)")
        self.assertFalse(same_story(a,b))


if __name__ == "__main__":
    unittest.main()
