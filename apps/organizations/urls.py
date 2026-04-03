from django.urls import path
from .views import MyOrganizationsView

urlpatterns = [
    path("my-organizations/", MyOrganizationsView.as_view(), name="my-organizations"),
]