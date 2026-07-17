"""Backward-compatible imports. Prefer dedicated collector modules."""
from .analytics import AnalyticsCollector
from .google_business import BusinessProfileCollector
from .search_console import SearchConsoleCollector
__all__ = ["AnalyticsCollector", "BusinessProfileCollector", "SearchConsoleCollector"]
