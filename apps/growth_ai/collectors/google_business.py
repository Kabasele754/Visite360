from .base import BaseCollector, CollectorResult
from .http import request_json

class BusinessProfileCollector(BaseCollector):
    provider = "business_profile"

    def collect(self, start_date, end_date):
        token = self.credentials.get("access_token")
        locations = self.config.get("location_names", [])
        if not token or not locations:
            raise ValueError("Google Business Profile requires access_token and config.location_names")
        metrics = self.config.get("metrics", [
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS", "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
            "WEBSITE_CLICKS", "CALL_CLICKS", "BUSINESS_DIRECTION_REQUESTS",
        ])
        rows = []
        for location in locations:
            params = [("dailyMetrics", metric) for metric in metrics]
            params += [
                ("dailyRange.startDate.year", start_date.year), ("dailyRange.startDate.month", start_date.month),
                ("dailyRange.startDate.day", start_date.day), ("dailyRange.endDate.year", end_date.year),
                ("dailyRange.endDate.month", end_date.month), ("dailyRange.endDate.day", end_date.day),
            ]
            data = request_json(
                f"https://businessprofileperformance.googleapis.com/v1/{location}:fetchMultiDailyMetricsTimeSeries",
                headers={"Authorization": f"Bearer {token}"}, params=params,
            )
            by_date = {}
            for series in data.get("multiDailyMetricTimeSeries", []):
                metric_name = series.get("dailyMetric", "metric").lower()
                for point in series.get("timeSeries", {}).get("datedValues", []):
                    value_date = point.get("date", {})
                    date_key = f"{value_date.get('year'):04d}-{value_date.get('month'):02d}-{value_date.get('day'):02d}"
                    by_date.setdefault(date_key, {})[metric_name] = point.get("value", 0)
            rows.extend({"date": day, "dimensions": {"location": location}, "metrics": values} for day, values in by_date.items())
        return CollectorResult(len(rows), self.save_rows(rows), {"locations": len(locations)})
