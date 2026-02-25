"""
Class for Exception Handling and Extracting data out of complex strings
"""
import asyncio
import httpx
from bs4 import BeautifulSoup

from .performance import Performance
from .sorting import Sorting


class Extractor(Performance):
    def __init__(self):
        super().__init__()
        self.sorting = Sorting()
        self.headers = self.headers()

    # Extracting Author Name
    def _author_name_extractor(self, name: str):
        author_name = self.remove_symbols(self._pattern1.sub("", name))

        if not self.is_valid_author_name(author_name):
            return "N/A"
        return self.format_author_name(author_name)

    # Checking if advertisement
    def _check_ad(self, news_date: str):
        return self._pattern4.search(news_date) is not None

    # Extracting News Date
    def _news_date_extractor(self, date: str, news_date: str) -> str:
        date = self._pattern3.sub("", self._pattern2.sub("", date))
        return self._pattern5.match(date).group() if news_date != "" else "N/A"

    # Extracting Data From Single News
    async def _extract_data_from_single_news(self, client, url: str, value: dict):
        news_data_from_single_news = []

        try:
            response = await client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
        except (httpx.RequestError, httpx.TimeoutException) as e:
            print(f"Request to {url} failed: {e}")
            return []

        news_headlines = soup.select(value["headlines"])
        raw_news_author = (
            soup.select(value["author"]) if value["author"] is not None else ""
        )
        news_full_news = soup.select(value["fullNews"])
        news_url = soup.select(value["newsURL"])
        news_img_url = soup.select(value["newsImg"])
        raw_news_date = soup.select(value["date"]) if value["date"] is not None else ""

        for index in range(len(news_headlines)):

            news_date = (
                self._news_date_extractor(
                    raw_news_date[index].text.strip(), raw_news_date
                )
                if raw_news_date
                else "N/A"
            )

            news_author = (
                self._author_name_extractor(raw_news_author[index].text.strip())
                if raw_news_author
                else "N/A"
            )

            if self._check_ad(news_date):
                continue

            if not self.valid_url_check(news_url[index]["href"]):
                continue

            if self.spam_content_check(
                news_headlines[index].text.strip() + " " +
                news_full_news[index].text.strip()
            ):
                continue

            complete_news = {
                "id": self.sorting.ordering_date(news_date),
                "headlines": news_headlines[index].text.strip(),
                "author": news_author,
                "fullNews": news_full_news[index].text.strip(),
                "newsURL": news_url[index]["href"],
                "newsImgURL": news_img_url[index]["data-src"],
                "newsDate": news_date,
            }

            news_data_from_single_news.append(complete_news)

        unique_news = self._remove_duplicates(news_data_from_single_news)
        return self.sorting.ordering_news(unique_news)

    # ✅ FIXED: Properly aligned async extractor
    async def _async_data_extractor(self, news: list) -> list:
        news_data = []

        timeout = httpx.Timeout(
            connect=5.0,
            read=15.0,
            write=5.0,
            pool=5.0
        )

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=timeout
        ) as client:

            tasks = [
                self._extract_data_from_single_news(client, url, value)
                for single_news in news
                for url, value in single_news.items()
           ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    print(f"Scrape error: {result}")
                    continue
                news_data.extend(result)

        unique_news_data = self._remove_duplicates(news_data)
        return self.sorting.ordering_news(unique_news_data)

    def data_extractor(self, news: list) -> list:
        return asyncio.run(self._async_data_extractor(news))

    # Removing Duplicates
    def _remove_duplicates(self, news_data: list) -> list:
        seen = set()
        unique_news_data = []

        for item in news_data:
            identifier = (item["headlines"], item["newsURL"], item["newsDate"])
            if identifier not in seen:
                seen.add(identifier)
                unique_news_data.append(item)

        return unique_news_data