from urllib.parse import quote
from .base import BaseCollector, CollectorResult
from .http import request_json

class SearchConsoleCollector(BaseCollector):
    provider = "search_console"

    def collect(self, start_date, end_date):
        token = self.credentials.get("access_token")
        site = self.config.get("site_url")
        if not token or not site:
            raise ValueError("Search Console requires access_token and config.site_url")
        url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site, safe='')}/searchAnalytics/query"
        payload = {
            "startDate": str(start_date), "endDate": str(end_date),
            "dimensions": ["date", "query", "page", "country", "device"],
            "rowLimit": int(self.config.get("row_limit", 25000)),
        }
        data = request_json(url, headers={"Authorization": f"Bearer {token}"}, method="POST", body=payload)
        rows = []
        for item in data.get("rows", []):
            dimensions = dict(zip(payload["dimensions"], item.get("keys", [])))
            metric_date = dimensions.pop("date", str(end_date))
            rows.append({"date": metric_date, "dimensions": dimensions, "metrics": {
                "clicks": item.get("clicks", 0), "impressions": item.get("impressions", 0),
                "ctr": item.get("ctr", 0), "position": item.get("position", 0),
            }})
        return CollectorResult(len(rows), self.save_rows(rows), {"site_url": site})
