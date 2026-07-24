from __future__ import annotations

import re

from django import forms
from django.utils import timezone
from django.utils.text import slugify

from apps.domain_intelligence.models import (
    HealthcareFacilityProfile,
    HospitalityProfile,
    MedicalSpecialty,
    PropertyListingProfile,
)
from apps.places.models import Place

from .models import Tour


def _list_value(value: str) -> list[str]:
    values = []
    for item in re.split(r"[,;\n]+", str(value or "")):
        cleaned = " ".join(item.split()).strip()
        if cleaned and cleaned.casefold() not in {existing.casefold() for existing in values}:
            values.append(cleaned[:120])
    return values[:100]


def _list_initial(value) -> str:
    return ", ".join(str(item) for item in (value or []) if item)


class TourForm(forms.ModelForm):
    # Real-estate profile. These fields remain optional and are stored only when
    # the selected Place belongs to a real-estate category.
    property_listing_type = forms.ChoiceField(
        label="Listing type",
        choices=PropertyListingProfile.ListingType.choices,
        required=False,
    )
    property_type = forms.ChoiceField(
        label="Property type",
        choices=PropertyListingProfile.PropertyType.choices,
        required=False,
    )
    property_bathrooms = forms.DecimalField(
        label="Bathrooms",
        min_value=0,
        max_value=99,
        decimal_places=1,
        required=False,
    )
    property_parking_spaces = forms.IntegerField(label="Parking spaces", min_value=0, required=False)
    property_furnished = forms.BooleanField(label="Furnished", required=False)
    property_area_sqm = forms.DecimalField(label="Area (m²)", min_value=0, decimal_places=2, required=False)
    property_currency = forms.CharField(label="Currency", max_length=8, required=False, initial="USD")
    property_available_from = forms.DateField(
        label="Available from",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    property_amenities = forms.CharField(
        label="Property amenities",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "parking, pool, security, garden, wifi"}),
        help_text="Separate amenities with commas.",
    )
    property_pet_friendly = forms.BooleanField(label="Pet friendly", required=False)
    property_availability_status = forms.ChoiceField(
        label="Availability",
        choices=PropertyListingProfile.AvailabilityStatus.choices,
        required=False,
    )

    # Hospitality profile.
    hospitality_star_rating = forms.DecimalField(
        label="Hotel rating",
        min_value=0,
        max_value=5,
        decimal_places=1,
        required=False,
    )
    hospitality_room_count = forms.IntegerField(label="Room count", min_value=0, required=False)
    hospitality_price_from = forms.DecimalField(label="Price from", min_value=0, decimal_places=2, required=False)
    hospitality_currency = forms.CharField(label="Hotel currency", max_length=8, required=False, initial="USD")
    hospitality_check_in_time = forms.TimeField(
        label="Check-in time",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    hospitality_check_out_time = forms.TimeField(
        label="Check-out time",
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    hospitality_amenities = forms.CharField(
        label="Hotel amenities",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "wifi, breakfast, pool, airport shuttle"}),
        help_text="Separate amenities with commas.",
    )
    hospitality_booking_url = forms.URLField(label="Hotel booking URL", required=False)
    hospitality_is_available = forms.BooleanField(label="Accepting reservations", required=False, initial=True)

    # Healthcare facility profile.
    healthcare_appointment_phone = forms.CharField(label="Appointment phone", max_length=60, required=False)
    healthcare_appointment_email = forms.EmailField(label="Appointment email", required=False)
    healthcare_appointment_url = forms.URLField(label="Appointment URL", required=False)
    healthcare_emergency_phone = forms.CharField(label="Emergency phone", max_length=60, required=False)
    healthcare_accepts_walk_ins = forms.BooleanField(label="Accepts walk-ins", required=False)
    healthcare_telemedicine_available = forms.BooleanField(label="Telemedicine available", required=False)
    healthcare_specialties = forms.CharField(
        label="Medical specialties",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Cardiology, Orthopaedics, General surgery"}),
        help_text="Separate specialties with commas. Doctors can be synchronized from the official website or managed in Admin.",
    )
    healthcare_insurance_providers = forms.CharField(
        label="Insurance providers",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Discovery Health, Bonitas"}),
        help_text="Separate insurance providers with commas.",
    )

    class Meta:
        model = Tour
        fields = [
            "title",
            "place",
            "description",
            "thumbnail_image",
            "video_tour",
            "virtual_tour_url",
            "status",
            "version",
            "tour_date",
            "duration",
            "price",
            "is_featured",
            "max_participants",
            "guide_name",
            "contact_email",
            "location",
            "lat",
            "lng",
            "radius",
            "chambres",
            "balcon",
            "floor_number",
            "parking",
            "ascenseur",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Enter tour title"}),
            "description": forms.Textarea(attrs={"placeholder": "Write a short description..."}),
            "virtual_tour_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "tour_date": forms.DateInput(attrs={"type": "date"}),
            "duration": forms.TextInput(attrs={"placeholder": "HH:MM:SS"}),
            "price": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "version": forms.NumberInput(attrs={"min": "1"}),
            "max_participants": forms.NumberInput(attrs={"min": "1"}),
            "lat": forms.NumberInput(attrs={"step": "any", "placeholder": "Latitude"}),
            "lng": forms.NumberInput(attrs={"step": "any", "placeholder": "Longitude"}),
            "radius": forms.NumberInput(attrs={"step": "0.1"}),
            "chambres": forms.NumberInput(attrs={"min": "0"}),
            "floor_number": forms.NumberInput(),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)

        if organization:
            self.fields["place"].queryset = organization.places.order_by("name")

        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_class} form-control".strip()

        self.fields["thumbnail_image"].widget.attrs.update({
            "accept": "image/*",
            "data-upload-type": "image",
        })
        self.fields["video_tour"].widget.attrs.update({
            "accept": "video/*",
            "data-upload-type": "video",
        })

        if self.is_bound or not getattr(self.instance, "pk", None) or not getattr(self.instance, "place_id", None):
            return
        place = self.instance.place
        try:
            profile = place.property_profile
        except PropertyListingProfile.DoesNotExist:
            profile = None
        if profile:
            self.initial.update({
                "property_listing_type": profile.listing_type,
                "property_type": profile.property_type,
                "property_bathrooms": profile.bathrooms,
                "property_parking_spaces": profile.parking_spaces,
                "property_furnished": profile.furnished,
                "property_area_sqm": profile.area_sqm,
                "property_currency": profile.currency,
                "property_available_from": profile.available_from,
                "property_amenities": _list_initial(profile.amenities),
                "property_pet_friendly": profile.pet_friendly,
                "property_availability_status": profile.availability_status,
            })
        try:
            hotel = place.hospitality_profile
        except HospitalityProfile.DoesNotExist:
            hotel = None
        if hotel:
            self.initial.update({
                "hospitality_star_rating": hotel.star_rating,
                "hospitality_room_count": hotel.room_count,
                "hospitality_price_from": hotel.price_from,
                "hospitality_currency": hotel.currency,
                "hospitality_check_in_time": hotel.check_in_time,
                "hospitality_check_out_time": hotel.check_out_time,
                "hospitality_amenities": _list_initial(hotel.amenities),
                "hospitality_booking_url": hotel.booking_url,
                "hospitality_is_available": hotel.is_available,
            })
        try:
            facility = place.healthcare_profile
        except HealthcareFacilityProfile.DoesNotExist:
            facility = None
        if facility:
            self.initial.update({
                "healthcare_appointment_phone": facility.appointment_phone,
                "healthcare_appointment_email": facility.appointment_email,
                "healthcare_appointment_url": facility.appointment_url,
                "healthcare_emergency_phone": facility.emergency_phone,
                "healthcare_accepts_walk_ins": facility.accepts_walk_ins,
                "healthcare_telemedicine_available": facility.telemedicine_available,
                "healthcare_specialties": _list_initial(facility.specialties),
                "healthcare_insurance_providers": _list_initial(facility.insurance_providers),
            })

    def save_domain_profiles(self, tour: Tour) -> None:
        """Persist the optional business profile matching the selected Place."""
        if not self.is_valid() or not tour.place_id:
            return
        cleaned = self.cleaned_data
        category = tour.place.category
        real_estate_categories = {
            Place.Category.HOUSE, Place.Category.APARTMENT, Place.Category.VILLA,
            Place.Category.STUDIO, Place.Category.OFFICE, Place.Category.BUILDING,
            Place.Category.LAND, Place.Category.REAL_ESTATE,
        }
        hospitality_categories = {
            Place.Category.HOTEL, Place.Category.RESORT,
            Place.Category.GUEST_HOUSE, Place.Category.LODGE,
        }
        healthcare_categories = {
            Place.Category.HOSPITAL, Place.Category.CLINIC,
            Place.Category.DENTAL_CLINIC, Place.Category.PHARMACY,
        }
        if category in real_estate_categories:
            type_map = {
                Place.Category.HOUSE: PropertyListingProfile.PropertyType.HOUSE,
                Place.Category.APARTMENT: PropertyListingProfile.PropertyType.APARTMENT,
                Place.Category.VILLA: PropertyListingProfile.PropertyType.VILLA,
                Place.Category.STUDIO: PropertyListingProfile.PropertyType.STUDIO,
                Place.Category.OFFICE: PropertyListingProfile.PropertyType.OFFICE,
                Place.Category.BUILDING: PropertyListingProfile.PropertyType.BUILDING,
                Place.Category.LAND: PropertyListingProfile.PropertyType.LAND,
            }
            amenities = set(_list_value(cleaned.get("property_amenities")))
            for enabled, name in ((tour.parking, "parking"), (tour.balcon, "balcony"), (tour.ascenseur, "elevator")):
                if enabled:
                    amenities.add(name)
            PropertyListingProfile.objects.update_or_create(
                place=tour.place,
                defaults={
                    "listing_type": cleaned.get("property_listing_type") or PropertyListingProfile.ListingType.RENT,
                    "property_type": cleaned.get("property_type") or type_map.get(category, PropertyListingProfile.PropertyType.OTHER),
                    "bedrooms": max(0, tour.chambres or 0),
                    "bathrooms": cleaned.get("property_bathrooms") or 0,
                    "parking_spaces": cleaned.get("property_parking_spaces") or int(bool(tour.parking)),
                    "furnished": bool(cleaned.get("property_furnished")),
                    "area_sqm": cleaned.get("property_area_sqm"),
                    "price": tour.price,
                    "currency": (cleaned.get("property_currency") or "USD").upper(),
                    "available_from": cleaned.get("property_available_from"),
                    "amenities": sorted(amenities),
                    "pet_friendly": bool(cleaned.get("property_pet_friendly")),
                    "availability_status": cleaned.get("property_availability_status") or PropertyListingProfile.AvailabilityStatus.AVAILABLE,
                    "verified_at": timezone.now(),
                },
            )
        elif category in hospitality_categories:
            HospitalityProfile.objects.update_or_create(
                place=tour.place,
                defaults={
                    "star_rating": cleaned.get("hospitality_star_rating"),
                    "room_count": cleaned.get("hospitality_room_count"),
                    "price_from": cleaned.get("hospitality_price_from") or tour.price,
                    "currency": (cleaned.get("hospitality_currency") or "USD").upper(),
                    "check_in_time": cleaned.get("hospitality_check_in_time"),
                    "check_out_time": cleaned.get("hospitality_check_out_time"),
                    "amenities": _list_value(cleaned.get("hospitality_amenities")),
                    "booking_url": cleaned.get("hospitality_booking_url") or "",
                    "is_available": bool(cleaned.get("hospitality_is_available")),
                    "verified_at": timezone.now(),
                },
            )
        elif category in healthcare_categories:
            specialties = _list_value(cleaned.get("healthcare_specialties"))
            HealthcareFacilityProfile.objects.update_or_create(
                place=tour.place,
                defaults={
                    "appointment_phone": cleaned.get("healthcare_appointment_phone") or "",
                    "appointment_email": cleaned.get("healthcare_appointment_email") or "",
                    "appointment_url": cleaned.get("healthcare_appointment_url") or "",
                    "emergency_phone": cleaned.get("healthcare_emergency_phone") or "",
                    "accepts_walk_ins": bool(cleaned.get("healthcare_accepts_walk_ins")),
                    "telemedicine_available": bool(cleaned.get("healthcare_telemedicine_available")),
                    "specialties": specialties,
                    "insurance_providers": _list_value(cleaned.get("healthcare_insurance_providers")),
                    "verified_at": timezone.now(),
                    "is_active": True,
                },
            )
            for name in specialties:
                MedicalSpecialty.objects.update_or_create(
                    organization=tour.organization,
                    slug=slugify(name)[:200] or "general-medicine",
                    defaults={
                        "name": name,
                        "verified_at": timezone.now(),
                        "is_active": True,
                    },
                )
