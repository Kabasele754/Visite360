from django import forms
from .models import ContactLead


class ContactLeadForm(forms.ModelForm):
    class Meta:
        model = ContactLead
        fields = [
            "full_name",
            "email",
            "phone",
            "company_name",
            "service_interest",
            "subject",
            "message",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={
                "placeholder": "Your full name",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "you@example.com",
            }),
            "phone": forms.TextInput(attrs={
                "placeholder": "+1 234 567 890",
            }),
            "company_name": forms.TextInput(attrs={
                "placeholder": "Company or brand name",
            }),
            "service_interest": forms.Select(),
            "subject": forms.TextInput(attrs={
                "placeholder": "Tell us what you need",
            }),
            "message": forms.Textarea(attrs={
                "placeholder": "Describe your project, space, or goals...",
                "rows": 6,
            }),
        }


