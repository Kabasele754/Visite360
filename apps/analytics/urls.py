from django.urls import path
from .views import AnalyticsEventCreateView

urlpatterns = [
    path("public/analytics/events/", AnalyticsEventCreateView.as_view(), name="analytics-event-create"),
]

