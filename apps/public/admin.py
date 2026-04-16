from django.contrib import admin
from .models import ContactLead

# Register your models here.

@admin.register(ContactLead)
class ContactLeadAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "service_interest", "subject", "is_processed", "created_at")
    list_filter = ("service_interest", "is_processed", "created_at")
    search_fields = ("full_name", "email", "company_name", "subject", "message")
    readonly_fields = ("created_at",)


