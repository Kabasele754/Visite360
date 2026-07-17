from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import AppointmentRequest, DeliveryZone, Order, ProductReview
from .customer_accounts import normalize_email


class CheckoutForm(forms.ModelForm):
    PAYMENT_CHOICES = (
        ("stripe", "Credit or debit card"),
        ("paypal", "PayPal"),
        ("manual", "Pay on delivery / pickup"),
    )
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        initial="stripe",
    )

    class Meta:
        model = Order
        fields = [
            "customer_name", "customer_email", "customer_phone", "fulfillment",
            "delivery_zone", "delivery_address", "delivery_suburb", "delivery_city",
            "delivery_province", "delivery_postal_code", "delivery_country_code",
            "customer_notes",
        ]
        widgets = {
            "customer_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Full name"}),
            "customer_email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "Email address"}),
            "customer_phone": forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "Phone number"}),
            "fulfillment": forms.Select(),
            "delivery_zone": forms.Select(),
            "delivery_address": forms.Textarea(attrs={"rows": 2, "autocomplete": "street-address", "placeholder": "Street address and useful directions"}),
            "delivery_suburb": forms.TextInput(attrs={"autocomplete": "address-level3", "placeholder": "Suburb"}),
            "delivery_city": forms.TextInput(attrs={"autocomplete": "address-level2", "placeholder": "City"}),
            "delivery_province": forms.TextInput(attrs={"autocomplete": "address-level1", "placeholder": "Province, e.g. Gauteng"}),
            "delivery_postal_code": forms.TextInput(attrs={"autocomplete": "postal-code", "placeholder": "Postal code"}),
            "delivery_country_code": forms.HiddenInput(),
            "customer_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional notes for the vendor or delivery team"}),
        }


    def clean(self):
        cleaned = super().clean()
        fulfillment = cleaned.get("fulfillment")
        zone = cleaned.get("delivery_zone")

        if fulfillment == Order.Fulfillment.DELIVERY:
            required = {
                "delivery_address": "Street address is required for delivery.",
                "delivery_city": "City is required for delivery.",
                "delivery_province": "Province is required for delivery.",
                "delivery_postal_code": "Postal code is required for delivery.",
            }
            for field, message in required.items():
                if not (cleaned.get(field) or "").strip():
                    self.add_error(field, message)

            country = (cleaned.get("delivery_country_code") or "ZA").upper()
            cleaned["delivery_country_code"] = country
            if country == "ZA":
                postal = (cleaned.get("delivery_postal_code") or "").replace(" ", "")
                if postal and (not postal.isdigit() or len(postal) != 4):
                    self.add_error(
                        "delivery_postal_code",
                        "South African postal codes must contain 4 digits.",
                    )

            if zone:
                city = (cleaned.get("delivery_city") or "").strip().casefold()
                province = (cleaned.get("delivery_province") or "").strip().casefold()
                postal = (cleaned.get("delivery_postal_code") or "").strip()

                if zone.country_code and zone.country_code.upper() != country:
                    self.add_error("delivery_zone", "The selected delivery zone does not support this country.")
                if zone.province and zone.province.lower() not in {"nationwide", "general"}:
                    if province and province != zone.province.strip().casefold():
                        self.add_error(
                            "delivery_province",
                            f"This zone is limited to {zone.province}.",
                        )
                if zone.cities:
                    allowed_cities = {str(item).strip().casefold() for item in zone.cities}
                    if city and city not in allowed_cities:
                        self.add_error(
                            "delivery_city",
                            "This city is outside the selected delivery zone.",
                        )
                if zone.postal_codes and postal not in {str(item) for item in zone.postal_codes}:
                    self.add_error(
                        "delivery_postal_code",
                        "This postal code is outside the selected delivery zone.",
                    )
        return cleaned

    def clean_customer_email(self):
        return normalize_email(self.cleaned_data["customer_email"])


class CustomerActivateForm(forms.Form):
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Create password")
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Confirm password")

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("new_password1")
        if password and password != cleaned.get("new_password2"):
            raise ValidationError("The passwords do not match.")
        if password:
            validate_password(password)
        return cleaned


class AppointmentRequestForm(forms.ModelForm):
    class Meta:
        model = AppointmentRequest
        fields = ["appointment_type", "full_name", "email", "phone", "preferred_date", "preferred_time", "notes"]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "preferred_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class DeliveryZoneForm(forms.ModelForm):
    cities_text = forms.CharField(
        required=False,
        label="Cities",
        help_text="Comma-separated, for example: Johannesburg, Sandton, Randburg",
        widget=forms.Textarea(attrs={
            "rows": 2,
            "placeholder": "Johannesburg, Sandton, Randburg",
        }),
    )
    postal_codes_text = forms.CharField(
        required=False,
        label="Postal codes",
        help_text="Optional comma-separated postal codes.",
        widget=forms.Textarea(attrs={
            "rows": 2,
            "placeholder": "2000, 2196, 2146",
        }),
    )

    class Meta:
        model = DeliveryZone
        fields = [
            "name",
            "country_code",
            "province",
            "currency",
            "fee",
            "free_delivery_threshold",
            "estimated_days_min",
            "estimated_days_max",
            "is_default",
            "is_active",
        ]
        widgets = {
            "country_code": forms.TextInput(attrs={"maxlength": 2, "placeholder": "ZA"}),
            "province": forms.TextInput(attrs={"placeholder": "Gauteng"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["cities_text"].initial = ", ".join(self.instance.cities or [])
            self.fields["postal_codes_text"].initial = ", ".join(self.instance.postal_codes or [])

    @staticmethod
    def _split_csv(value):
        return sorted({
            part.strip()
            for part in (value or "").split(",")
            if part.strip()
        })

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.cities = self._split_csv(self.cleaned_data.get("cities_text"))
        instance.postal_codes = self._split_csv(self.cleaned_data.get("postal_codes_text"))
        if commit:
            instance.save()
        return instance


class ProductReviewForm(forms.ModelForm):
    images = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = ProductReview
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(value, f"{value} / 5") for value in range(5, 0, -1)]),
            "comment": forms.Textarea(attrs={"rows": 5, "placeholder": "Share your experience with this product."}),
        }
