import feedparser
from datetime import datetime


class RSSFetcher:
    def __init__(self, feed_url):
        self.feed_url = feed_url

    def fetch(self, limit=20):
        feed = feedparser.parse(self.feed_url)
        items = []

        for entry in feed.entries[:limit]:
            items.append({
                "title": entry.get("title", ""),
                "source": self.feed_url,
                "date": self._parse_date(entry),
                "url": entry.get("link", "")
            })

        return items

    def _parse_date(self, entry):
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6]).strftime("%b %d, %Y")
        return ""