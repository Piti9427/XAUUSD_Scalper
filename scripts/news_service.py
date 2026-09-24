import datetime
import logging

# Note: In a real environment, we might use BeautifulSoup to scrape ForexFactory.
# For this implementation, we provide a robust structure that can be connected to an API or a scraper.


logger = logging.getLogger(__name__)


class NewsIntelligenceService:
    def __init__(self, config):
        self.config = config.get("news", {})
        self.enabled = self.config.get("enabled", False)
        self.impact_threshold = self.config.get("impact_threshold", "HIGH")
        self.pause_window_mins = self.config.get("pause_window_mins", 60)
        self.last_update = None
        self.upcoming_news = []
        if not self.enabled:
            logger.warning(
                "News filter is disabled placeholder; high-impact news is not being fetched."
            )

    def fetch_news(self):
        """
        In a production scenario, this would scrape ForexFactory or use a Financial Calendar API.
        For this version, we implement a placeholder that can be easily extended.
        """
        logger.warning(
            "News fetch is not implemented; returning configured in-memory news list only."
        )
        return []

    def is_safe_to_trade(self, symbol="USD"):
        """
        Checks if there are any high-impact news events for the currency within the pause window.
        Returns (is_safe, news_event_name)
        """
        if not self.enabled:
            return True, "NEWS_FILTER_DISABLED"

        now = datetime.datetime.now(datetime.timezone.utc)

        # In a real run, we would call fetch_news() periodically
        # self.upcoming_news = self.fetch_news()

        for event in self.upcoming_news:
            event_time = event.get("time")  # Expected to be UTC datetime
            if event.get("impact") == self.impact_threshold and event.get("currency") in [
                symbol,
                "USD",
            ]:
                time_diff = (event_time - now).total_seconds() / 60

                # If news is within the window (before or shortly after)
                if -15 < time_diff < self.pause_window_mins:
                    return False, event.get("name")

        return True, None

    def update_news_data(self, news_list):
        """Allows external update of news data (e.g. from a main scraper)."""
        self.upcoming_news = news_list
        self.last_update = datetime.datetime.now()
