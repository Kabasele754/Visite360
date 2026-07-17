from .base import BaseCollector, CollectorResult
from .http import request_json

class AnalyticsCollector(BaseCollector):
    provider = "analytics"

    def collect(self, start_date, end_date):
        token = self.credentials.get("access_token")
        property_id = self.config.get("property_id")
        if not token or not property_id:
            raise ValueError("GA4 requires access_token and config.property_id")
        url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
        names = ["activeUsers", "sessions", "screenPageViews", "engagedSessions", "averageSessionDuration", "conversions"]
        payload = {
            "dateRanges": [{"startDate": str(start_date), "endDate": str(end_date)}],
            "dimensions": [{"name": name} for name in ["date", "sessionSource", "deviceCategory", "pagePath"]],
            "metrics": [{"name": name} for name in names],
            "limit": str(self.config.get("row_limit", 100000)),
        }
        data = request_json(url, headers={"Authorization": f"Bearer {token}"}, method="POST", body=payload)
        rows = []
        metric_keys = ["active_users", "sessions", "pageviews", "engaged_sessions", "avg_session_duration", "conversions"]
        for item in data.get("rows", []):
            dims = [x.get("value", "") for x in item.get("dimensionValues", [])]
            values = [x.get("value", "0") for x in item.get("metricValues", [])]
            if len(dims) < 4:
                continue
            date_raw = dims[0]
            metric_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
            rows.append({"date": metric_date, "dimensions": {"source": dims[1], "device": dims[2], "page": dims[3]}, "metrics": dict(zip(metric_keys, values))})
        return CollectorResult(len(rows), self.save_rows(rows), {"property_id": property_id})
