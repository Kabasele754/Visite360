from django.contrib import admin

from apps.organizations.models import Organization
from apps.places.models import Place

# Register your models here.



admin.site.register(Organization)
admin.site.register(Place)



