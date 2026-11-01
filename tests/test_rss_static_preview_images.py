"""Offline safety checks for real story images in the static RSS pipeline."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from newsbot.core import parse_feed, render_outputs
from newsbot.dashboard_export import read_news, build_bundle
from newsbot.rss_images import safe_image_url, article_image

NOW=datetime(2026,11,1,2,0,tzinfo=timezone.utc)

def rss(inner):
    return (
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>'
        '<title>My Publisher</title><image><url>https://publisher.example/logo.jpg</url></image>'
        '<item><title>Enterprise technology company launches product</title>'
        '<link>https://publisher.example/story</link>'
        '<pubDate>Sun, 01 Nov 2026 01:30:00 GMT</pubDate>'
        '<description>Enterprise technology product launch update.</description>'
        +inner+'</item></channel></rss>'
    ).encode()

class RSSStaticImageTests(unittest.TestCase):
    def test_news_entry_thumbnail_not_website_logo(self):
        data=parse_feed(rss('<media:thumbnail url="https://cdn.publisher.example/news.webp" width="640" height="360"/>'),"Example")
        self.assertEqual(len(data),1)
        self.assertEqual(data[0].image_url,"https://cdn.publisher.example/news.webp")
        self.assertEqual(parse_feed(rss(""),"Example")[0].image_url,"")
        self.assertEqual(parse_feed(rss('<media:thumbnail url="https://cdn.publisher.example/tiny.png" width="1" height="1"/>'),"Example")[0].image_url,"")

    def test_image_enclosure_and_no_network_or_unsafe_urls(self):
        xml=rss('<enclosure type="image/jpeg" url="https://cdn.publisher.example/story.jpg"/>')
        self.assertEqual(parse_feed(xml,"Example")[0].image_url,"https://cdn.publisher.example/story.jpg")
        for candidate in (
            "http://cdn.example/photo.jpg","javascript:alert(1)","https://localhost/image.jpg",
            "https://127.0.0.1/photo.jpg","https://cdn.example/payload.svg",
            "https://cdn.example/animation.gif","https://user:pass@cdn.example/photo.png",
            "https://cdn.example:8443/photo.png","https://cdn.example/a.jpg%0aevil"
        ):
            self.assertEqual(safe_image_url(candidate),"",candidate)

    def test_public_static_bundle_preserves_publisher_rss_image(self):
        article=parse_feed(rss('<media:content medium="image" url="https://cdn.publisher.example/cover.jpg"/>'),"Example")[0]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            render_outputs([article],root,NOW,[],preview_only=True)
            queue=json.loads((root/"review_queue.json").read_text("utf-8"))
            self.assertEqual(queue["articles"][0]["image_url"],"https://cdn.publisher.example/cover.jpg")
            public=read_news(queue)
            self.assertEqual(public[0]["image_url"],"https://cdn.publisher.example/cover.jpg")
            bundle=build_bundle(queue,[],root/"site")
            self.assertEqual(bundle["news"][0]["image_url"],public[0]["image_url"])

    def test_article_description_embedded_html_image_is_used(self):
        detail=(
            '<description><![CDATA[<p>Story preview</p><figure><img '
            'src="https://cdn.publisher.example/article-cover.webp" width="800" '
            'height="500" /></figure>]]></description>'
        )
        article=parse_feed(rss(detail),"Example")[0]
        self.assertEqual(article.image_url,
                         "https://cdn.publisher.example/article-cover.webp")
        # No content on the channel itself is ever borrowed for a story.
        article=parse_feed(rss("<description>Plain publisher summary</description>"),"Example")[0]
        self.assertEqual(article.image_url,"")

    def test_content_encoded_html_and_lazy_srcset(self):
        prefix='<content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/"><![CDATA['
        html='<picture><img src="https://publisher.example/placeholder.png" data-src="https://cdn.publisher.example/photo.jpg" /></picture>'
        article=parse_feed(rss(prefix+html+']]></content:encoded>'),"Example")[0]
        self.assertEqual(article.image_url,"https://cdn.publisher.example/photo.jpg")
        html='<img srcset="https://cdn.publisher.example/photo-small.jpg 120w, https://cdn.publisher.example/photo-large.jpg 800w">'
        article=parse_feed(rss(prefix+html+']]></content:encoded>'),"Example")[0]
        self.assertEqual(article.image_url,"https://cdn.publisher.example/photo-large.jpg")

    def test_prefer_explicit_media_and_ignore_tracking_or_unusable_embedded_images(self):
        detail=(
            '<description><![CDATA[<img src="https://publisher.example/avatar.jpg"/>'
            '<img src="https://publisher.example/tracker.png" width="1" height="1">'
            '<img src="https://publisher.example/valid-photo.webp"/>]]></description>'
        )
        article=parse_feed(rss(detail),"Example")[0]
        self.assertEqual(article.image_url,"https://publisher.example/valid-photo.webp")
        explicit='<media:thumbnail url="https://cdn.publisher.example/hero.jpg" />'+detail
        self.assertEqual(parse_feed(rss(explicit),"Example")[0].image_url,
                         "https://cdn.publisher.example/hero.jpg")
        for bad in (
            'src="https://publisher.example/logo.jpg"',
            'src="https://publisher.example/square-icon.png"',
            'src="http://publisher.example/insecure.jpg"',
            'src="https://publisher.example/photo.svg"',
            'src="https://publisher.example/pixel.jpg" width="2" height="2"',
        ):
            article=parse_feed(rss('<description><![CDATA[<img '+bad+'/>]]></description>'),"Example")[0]
            self.assertEqual(article.image_url,"",bad)

    def test_grouped_media_content(self):
        image='<media:group><media:content url="https://cdn.publisher.example/report.png" type="image/png" width="700" height="410" /></media:group>'
        article=parse_feed(rss(image),"Example")[0]
        self.assertEqual(article.image_url,"https://cdn.publisher.example/report.png")

    def test_preview_data_limits_are_50_without_modifying_publishing(self):
        shell=Path("scripts/build_cloudflare_preview.sh").read_text()
        cli=Path("newsbot/__main__.py").read_text()
        region=Path("newsbot/regions.py").read_text()
        core=Path("newsbot/core.py").read_text()
        self.assertIn("--dashboard-limit 50",shell)
        self.assertIn("9 <= args.dashboard_limit <= 50",cli)
        self.assertIn("max_articles=50",region)
        self.assertIn("for item in (india_articles or [])[:50]",core)
        self.assertIn("PUBLISH_ENABLED=false",shell)

if __name__=="__main__":
    unittest.main()
