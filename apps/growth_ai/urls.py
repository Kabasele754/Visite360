from django.urls import path
from . import views
app_name='growth_ai'
urlpatterns=[path('dashboard/o/<slug:organization_slug>/growth/',views.dashboard,name='dashboard'),path('dashboard/o/<slug:organization_slug>/growth/sources/<int:connection_id>/sync/',views.sync_now,name='sync_now'),path('api/growth/events/',views.collect_event,name='collect_event')]
