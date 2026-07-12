from django.db import models
from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization

class Place(TimeStampedModel):
    class Category(models.TextChoices):
        # Commerce
        STORE = "store", "Store"
        BOUTIQUE = "boutique", "Boutique"
        SUPERMARKET = "supermarket", "Supermarket"
        SHOPPING_MALL = "shopping_mall", "Shopping Mall"
        SHOWROOM = "showroom", "Showroom"
        PHARMACY = "pharmacy", "Pharmacy"
        BEAUTY_SALON = "beauty_salon", "Beauty Salon"
        BARBERSHOP = "barbershop", "Barbershop"

        # Wedding / Events
        WEDDING_HALL = "wedding_hall", "Wedding Hall"
        EVENT_HALL = "event_hall", "Event Hall"
        CONFERENCE_HALL = "conference_hall", "Conference Hall"
        BANQUET_HALL = "banquet_hall", "Banquet Hall"
        CHURCH = "church", "Church"
        CEREMONY_PLACE = "ceremony_place", "Ceremony Place"
        PARTY_VENUE = "party_venue", "Party Venue"

        # Real Estate
        HOUSE = "house", "House"
        APARTMENT = "apartment", "Apartment"
        VILLA = "villa", "Villa"
        STUDIO = "studio", "Studio"
        OFFICE = "office", "Office"
        BUILDING = "building", "Building"
        LAND = "land", "Land"
        REAL_ESTATE = "real_estate", "Real Estate"

        # Hospitality / Tourism
        HOTEL = "hotel", "Hotel"
        RESORT = "resort", "Resort"
        GUEST_HOUSE = "guest_house", "Guest House"
        LODGE = "lodge", "Lodge"
        BEACH = "beach", "Beach"
        TOURIST_SITE = "tourist_site", "Tourist Site"
        MUSEUM = "museum", "Museum"
        PARK = "park", "Park"

        # Food / Nightlife
        RESTAURANT = "restaurant", "Restaurant"
        CAFE = "cafe", "Cafe"
        BAR = "bar", "Bar"
        LOUNGE = "lounge", "Lounge"
        CLUB = "club", "Club"
        FAST_FOOD = "fast_food", "Fast Food"

        # Health / Wellness
        HOSPITAL = "hospital", "Hospital"
        CLINIC = "clinic", "Clinic"
        DENTAL_CLINIC = "dental_clinic", "Dental Clinic"
        SPA = "spa", "Spa"
        GYM = "gym", "Gym"
        FITNESS_CENTER = "fitness_center", "Fitness Center"

        # Education
        SCHOOL = "school", "School"
        UNIVERSITY = "university", "University"
        TRAINING_CENTER = "training_center", "Training Center"
        LIBRARY = "library", "Library"

        # Business / Public Services
        COMPANY = "company", "Company"
        BANK = "bank", "Bank"
        GOVERNMENT_OFFICE = "government_office", "Government Office"
        COWORKING_SPACE = "coworking_space", "Coworking Space"

        # Transport
        AIRPORT = "airport", "Airport"
        BUS_STATION = "bus_station", "Bus Station"
        CAR_DEALERSHIP = "car_dealership", "Car Dealership"
        GARAGE = "garage", "Garage"

        # Other
        OTHER = "other", "Other"


    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="places")
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=40, choices=Category.choices)
    description = models.TextField(blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    cover_image = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["city", "category"]),
        ]

    def __str__(self):
        return self.name