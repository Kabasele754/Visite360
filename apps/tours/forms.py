from django import forms
from .models import Tour


class TourForm(forms.ModelForm):
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