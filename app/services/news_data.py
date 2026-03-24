from __future__ import annotations

from dataclasses import dataclass
import html
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from typing import List

import requests


@dataclass
class NewsHeadline:
    title: str
    link: str
    published: str


class GoogleNewsRssService:
    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, timeout_seconds: int = 12) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, query: str, limit: int = 8) -> List[NewsHeadline]:
        if not query.strip():
            return []

        url = f"{self.BASE_URL}?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        xml_text = requests.get(url, timeout=self.timeout_seconds).text
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        headlines: List[NewsHeadline] = []
        for item in channel.findall("item")[:limit]:
            title = html.unescape((item.findtext("title") or "").strip())
            link = (item.findtext("link") or "").strip()
            published = (item.findtext("pubDate") or "").strip()
            if not title:
                continue
            headlines.append(NewsHeadline(title=title, link=link, published=published))
        return headlines

    @staticmethod
    def to_signal_text(headlines: List[NewsHeadline]) -> str:
        return "\n".join(headline.title for headline in headlines)

