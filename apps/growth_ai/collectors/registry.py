from apps.growth_ai.models import Provider
from .analytics import AnalyticsCollector
from .bing import BingCollector
from .google_business import BusinessProfileCollector
from .internal import InternalCollector
from .search_console import SearchConsoleCollector
from .trends import GoogleTrendsCollector

MAP = {
    Provider.SEARCH_CONSOLE: SearchConsoleCollector,
    Provider.ANALYTICS: AnalyticsCollector,
    Provider.BUSINESS_PROFILE: BusinessProfileCollector,
    Provider.GOOGLE_TRENDS: GoogleTrendsCollector,
    Provider.BING: BingCollector,
    Provider.INTERNAL: InternalCollector,
}

def get_collector(connection):
    collector_class = MAP.get(connection.provider)
    if collector_class is None:
        raise ValueError(f"Unsupported Growth AI provider: {connection.provider}")
    return collector_class(connection)
