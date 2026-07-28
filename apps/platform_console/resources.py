from __future__ import annotations

from dataclasses import dataclass

from apps.ai_core.models import AIProviderConfiguration, AIRun
from apps.analytics.models import AnalyticsEvent
from apps.domain_intelligence.models import (
    DiscoverySearchLog,
    VerifiedSourceFact,
    HealthcareFacilityProfile,
    HospitalityProfile,
    MedicalPractitioner,
    MedicalSpecialty,
    OrganizationIntelligenceProfile,
    OrganizationIntelligenceRun,
    IntelligenceReviewItem,
    OrganizationEmbeddedResource,
    PractitionerAvailability,
    PropertyListingProfile,
)
from apps.knowledge.models import KnowledgeSource, ServiceOffering
from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour
from apps.users.models import User
from apps.vendors.models import AppointmentRequest, Order, Product, ProductCategory
from apps.vision_ai.models import VisionAnalysis


@dataclass(frozen=True)
class ResourceDefinition:
    key: str
    label: str
    singular: str
    icon: str
    model: type
    columns: tuple[tuple[str, str], ...]
    search_fields: tuple[str, ...] = ()
    form_fields: tuple[str, ...] = ()
    select_related: tuple[str, ...] = ()
    order_by: tuple[str, ...] = ("-created_at",)
    readonly: bool = False
    allow_delete: bool = True
    description: str = ""


RESOURCE_DEFINITIONS = {

    "users": ResourceDefinition(
        key="users", label="Users", singular="User", icon="👥", model=User,
        columns=(("email", "Email"), ("username", "Username"), ("is_active", "Active"), ("is_staff", "Staff"), ("date_joined", "Joined")),
        search_fields=("email", "username", "first_name", "last_name", "phone"),
        form_fields=("email", "username", "first_name", "last_name", "phone", "is_active", "is_customer", "preferred_currency"),
        order_by=("-date_joined",), allow_delete=False, description="Manage public account details and account activation without exposing passwords.",
    ),
    "ai-providers": ResourceDefinition(
        key="ai-providers", label="AI provider configuration", singular="AI provider configuration", icon="⚙️", model=AIProviderConfiguration,
        columns=(("organization", "Organization"), ("provider", "Provider"), ("capability", "Capability"), ("model_name", "Model"), ("is_enabled", "Enabled"), ("last_health_status", "Health")),
        search_fields=("organization__name", "provider", "capability", "model_name", "last_health_status"),
        form_fields=("organization", "provider", "capability", "model_name", "credential_reference", "settings", "priority", "is_enabled", "last_health_status", "last_health_message", "last_health_checked_at"),
        select_related=("organization",), description="Configure model routing using secret references, never raw API keys.",
    ),
    "verified-facts": ResourceDefinition(
        key="verified-facts", label="Verified source facts", singular="Verified source fact", icon="✓", model=VerifiedSourceFact,
        columns=(("organization", "Organization"), ("entity_type", "Entity"), ("field_name", "Field"), ("source_url", "Source"), ("confidence", "Confidence"), ("verified_at", "Verified")),
        search_fields=("organization__name", "place__name", "entity_type", "entity_key", "field_name", "source_url"),
        form_fields=("organization", "place", "entity_type", "entity_key", "field_name", "value", "source_url", "confidence", "verified_at", "expires_at", "is_public"),
        select_related=("organization", "place"), description="Review and correct facts collected from official organization websites.",
    ),
    "product-categories": ResourceDefinition(
        key="product-categories", label="Product categories", singular="Product category", icon="🏷️", model=ProductCategory,
        columns=(("name", "Name"), ("slug", "Slug"), ("is_active", "Active"), ("created_at", "Created")),
        search_fields=("name", "slug", "description"),
        form_fields=("name", "slug", "description", "icon", "is_active"), order_by=("name",),
        description="Manage marketplace product classification.",
    ),
    "products": ResourceDefinition(
        key="products", label="Products", singular="Product", icon="🛍️", model=Product,
        columns=(("organization", "Organization"), ("name", "Product"), ("category", "Category"), ("price", "Price"), ("stock_quantity", "Stock"), ("status", "Status")),
        search_fields=("organization__name", "name", "slug", "sku", "category__name"),
        form_fields=("organization", "category", "name", "slug", "sku", "short_description", "description", "specifications", "cover_image", "price", "compare_at_price", "currency", "stock_quantity", "track_inventory", "delivery_available", "pickup_available", "estimated_delivery_days", "status", "is_featured"),
        select_related=("organization", "category"), description="Manage products visible inside virtual tours and marketplace pages.",
    ),
    "orders": ResourceDefinition(
        key="orders", label="Orders", singular="Order", icon="📦", model=Order,
        columns=(("reference", "Reference"), ("organization", "Organization"), ("customer_name", "Customer"), ("total", "Total"), ("status", "Status"), ("payment_status", "Payment"), ("created_at", "Created")),
        search_fields=("reference", "organization__name", "customer_name", "customer_email", "customer_phone", "status", "payment_status"),
        form_fields=("organization", "customer", "customer_name", "customer_email", "customer_phone", "fulfillment", "delivery_zone", "delivery_address", "delivery_city", "delivery_suburb", "delivery_province", "delivery_postal_code", "delivery_country_code", "customer_notes", "subtotal", "delivery_fee", "total", "currency", "status", "payment_status", "payment_provider", "payment_reference", "paid_at"),
        select_related=("organization", "customer", "delivery_zone"), allow_delete=False, description="Review fulfillment and payment status without deleting financial history.",
    ),
    "organizations": ResourceDefinition(
        key="organizations", label="Organizations", singular="Organization", icon="🏢", model=Organization,
        columns=(("name", "Name"), ("slug", "Slug"), ("status", "Status"), ("website_url", "Website"), ("created_at", "Created")),
        search_fields=("name", "slug", "website_url", "public_email", "public_phone"),
        form_fields=("name", "slug", "logo", "status", "description", "website_url", "booking_url", "public_email", "public_phone", "facebook_url", "instagram_url", "tiktok_url", "linkedin_url", "youtube_url", "ai_use_website", "ai_auto_discover_social_links", "ai_assistant_enabled", "ai_assistant_brand_mode", "ai_assistant_name", "ai_assistant_tagline", "ai_assistant_avatar", "ai_allow_embedded_resources"),
        description="Manage platform organizations, public contact details and AI website access.",
    ),
    "places": ResourceDefinition(
        key="places", label="Places", singular="Place", icon="📍", model=Place,
        columns=(("organization", "Organization"), ("name", "Name"), ("category", "Category"), ("city", "City"), ("status", "Status")),
        search_fields=("name", "slug", "city", "country", "organization__name"),
        form_fields=("organization", "name", "slug", "category", "description", "address_line", "city", "country", "latitude", "longitude", "cover_image", "status", "published_at"),
        select_related=("organization",), description="Manage searchable locations and their business category.",
    ),
    "tours": ResourceDefinition(
        key="tours", label="Virtual tours", singular="Virtual tour", icon="🌐", model=Tour,
        columns=(("organization", "Organization"), ("title", "Title"), ("place", "Place"), ("status", "Status"), ("is_featured", "Featured"), ("view_count", "Views")),
        search_fields=("title", "slug", "place__name", "organization__name", "location"),
        form_fields=("organization", "place", "title", "slug", "description", "thumbnail_source", "video_tour", "virtual_tour_url", "status", "tour_date", "duration", "price", "is_featured", "max_participants", "rating", "guide_name", "contact_email", "location", "lat", "lng", "radius", "chambres", "balcon", "floor_number", "parking", "ascenseur", "published_at"),
        select_related=("organization", "place"), description="Control published tours, featured visibility and searchable metadata.",
    ),
    "intelligence-profiles": ResourceDefinition(
        key="intelligence-profiles", label="AI domain profiles", singular="AI domain profile", icon="🧠", model=OrganizationIntelligenceProfile,
        columns=(("organization", "Organization"), ("domain_kind", "Domain"), ("auto_sync_website", "Auto sync"), ("last_sync_status", "Last status"), ("last_synced_at", "Last sync")),
        search_fields=("organization__name", "domain_kind", "last_sync_status"),
        form_fields=("organization", "domain_kind", "default_locale", "timezone", "country_code", "auto_sync_website", "website_sync_max_pages", "last_synced_at", "last_sync_status", "metadata"),
        select_related=("organization",), description="Configure healthcare, real-estate, hospitality and general AI behavior.",
    ),
    "embedded-resources": ResourceDefinition(
        key="embedded-resources", label="Embedded organization resources", singular="Embedded resource", icon="▣", model=OrganizationEmbeddedResource,
        columns=(("organization", "Organization"), ("label", "Resource"), ("kind", "Kind"), ("embed_mode", "Display"), ("is_verified", "Verified"), ("is_active", "Active")),
        search_fields=("organization__name", "label", "kind", "url", "description"),
        form_fields=("organization", "label", "kind", "url", "embed_mode", "button_label", "description", "allow_in_tour_agent", "is_verified", "is_active", "sandbox_permissions", "source_url", "verified_at", "metadata"),
        select_related=("organization",), order_by=("organization__name", "label"),
        description="Manage verified websites, booking systems, CRM forms and contact resources displayed safely inside the Tour AI modal.",
    ),
    "intelligence-runs": ResourceDefinition(
        key="intelligence-runs", label="Intelligence collection runs", singular="Intelligence collection run", icon="◉", model=OrganizationIntelligenceRun,
        columns=(("organization", "Organization"), ("status", "Status"), ("pages_crawled", "Pages"), ("documents_indexed", "Documents"), ("readiness_after", "Readiness"), ("created_at", "Created")),
        search_fields=("organization__name", "status", "task_id", "website_url", "error_code"),
        select_related=("organization", "requested_by"), readonly=True, allow_delete=False,
        description="Monitor official-website collection, structured extraction, indexing and readiness progress.",
    ),
    "intelligence-reviews": ResourceDefinition(
        key="intelligence-reviews", label="Intelligence review queue", singular="Intelligence review item", icon="✓", model=IntelligenceReviewItem,
        columns=(("organization", "Organization"), ("item_type", "Type"), ("label", "Suggestion"), ("confidence", "Confidence"), ("status", "Status"), ("created_at", "Created")),
        search_fields=("organization__name", "item_type", "target_model", "target_field", "label", "source_url", "status"),
        select_related=("organization", "place", "run", "reviewed_by"), readonly=True, allow_delete=False,
        description="Review conflicts and lower-confidence website facts before they replace curated client data.",
    ),
    "healthcare-facilities": ResourceDefinition(
        key="healthcare-facilities", label="Healthcare facilities", singular="Healthcare facility", icon="🏥", model=HealthcareFacilityProfile,
        columns=(("place", "Facility"), ("appointment_phone", "Appointment phone"), ("telemedicine_available", "Telemedicine"), ("is_active", "Active"), ("verified_at", "Verified")),
        search_fields=("place__name", "place__organization__name", "appointment_phone", "appointment_email"),
        form_fields=("place", "appointment_phone", "appointment_email", "appointment_url", "emergency_phone", "accepts_walk_ins", "telemedicine_available", "opening_hours", "specialties", "insurance_providers", "accessibility", "source_url", "verified_at", "is_active"),
        select_related=("place", "place__organization"), description="Manage public healthcare contact, booking and service information.",
    ),
    "medical-specialties": ResourceDefinition(
        key="medical-specialties", label="Medical specialties", singular="Medical specialty", icon="🩺", model=MedicalSpecialty,
        columns=(("organization", "Organization"), ("name", "Specialty"), ("default_duration_minutes", "Duration"), ("is_active", "Active"), ("verified_at", "Verified")),
        search_fields=("name", "slug", "organization__name", "description"),
        form_fields=("organization", "name", "slug", "description", "aliases", "default_duration_minutes", "source_url", "verified_at", "is_active"),
        select_related=("organization",), order_by=("name",), description="Manage searchable specialties and their public descriptions.",
    ),
    "practitioners": ResourceDefinition(
        key="practitioners", label="Medical practitioners", singular="Medical practitioner", icon="👨‍⚕️", model=MedicalPractitioner,
        columns=(("organization", "Organization"), ("full_name", "Name"), ("specialty", "Specialty"), ("booking_mode", "Booking"), ("is_active", "Active")),
        search_fields=("full_name", "professional_title", "specialty__name", "organization__name"),
        form_fields=("organization", "place", "specialty", "full_name", "professional_title", "bio", "languages", "public_phone", "public_email", "booking_url", "booking_mode", "show_public_phone", "show_public_email", "source_url", "verified_at", "is_active", "metadata"),
        select_related=("organization", "place", "specialty"), order_by=("full_name",), description="Manage doctors, public contacts, specialties and booking options.",
    ),
    "practitioner-availability": ResourceDefinition(
        key="practitioner-availability", label="Practitioner availability", singular="Availability slot", icon="🗓️", model=PractitionerAvailability,
        columns=(("practitioner", "Practitioner"), ("weekday", "Day"), ("starts_at", "Starts"), ("ends_at", "Ends"), ("appointment_mode", "Mode"), ("is_active", "Active")),
        search_fields=("practitioner__full_name", "location_label", "appointment_mode"),
        form_fields=("practitioner", "weekday", "starts_at", "ends_at", "location_label", "appointment_mode", "is_active"),
        select_related=("practitioner",), order_by=("weekday", "starts_at"), description="Manage recurring appointment availability.",
    ),
    "property-listings": ResourceDefinition(
        key="property-listings", label="Property listings", singular="Property listing", icon="🏠", model=PropertyListingProfile,
        columns=(("place", "Property"), ("listing_type", "Listing"), ("property_type", "Type"), ("bedrooms", "Bedrooms"), ("price", "Price"), ("availability_status", "Availability")),
        search_fields=("place__name", "place__city", "place__organization__name", "property_type", "listing_type"),
        form_fields=("place", "listing_type", "property_type", "bedrooms", "bathrooms", "parking_spaces", "furnished", "area_sqm", "price", "currency", "available_from", "amenities", "pet_friendly", "availability_status", "source_url", "verified_at"),
        select_related=("place", "place__organization"), description="Manage searchable rental, sale and short-stay property specifications.",
    ),
    "hospitality": ResourceDefinition(
        key="hospitality", label="Hospitality profiles", singular="Hospitality profile", icon="🏨", model=HospitalityProfile,
        columns=(("place", "Property"), ("star_rating", "Stars"), ("room_count", "Rooms"), ("price_from", "Price from"), ("is_available", "Available")),
        search_fields=("place__name", "place__city", "place__organization__name"),
        form_fields=("place", "star_rating", "room_count", "price_from", "currency", "check_in_time", "check_out_time", "amenities", "booking_url", "is_available", "source_url", "verified_at"),
        select_related=("place", "place__organization"), description="Manage hotels, lodges, pricing and booking details.",
    ),
    "appointments": ResourceDefinition(
        key="appointments", label="Appointment requests", singular="Appointment request", icon="📅", model=AppointmentRequest,
        columns=(("organization", "Organization"), ("full_name", "Guest"), ("preferred_date", "Preferred date"), ("practitioner_name", "Practitioner"), ("status", "Status"), ("created_at", "Received")),
        search_fields=("full_name", "email", "phone", "organization__name", "practitioner_name", "specialty_name"),
        form_fields=("organization", "tour", "place", "appointment_type", "full_name", "email", "phone", "preferred_date", "preferred_time", "notes", "source", "practitioner_name", "specialty_name", "reason_for_visit", "appointment_mode", "status"),
        select_related=("organization", "tour", "place", "appointment_type"), description="Review, confirm and complete appointment requests.",
    ),
    "knowledge-sources": ResourceDefinition(
        key="knowledge-sources", label="Knowledge sources", singular="Knowledge source", icon="📚", model=KnowledgeSource,
        columns=(("organization", "Organization"), ("name", "Source"), ("source_type", "Type"), ("status", "Status"), ("last_synced_at", "Last sync")),
        search_fields=("name", "url", "organization__name", "source_type", "status"),
        form_fields=("organization", "name", "source_type", "url", "file", "status", "crawl_same_domain_only", "max_pages", "schedule", "metadata", "last_synced_at", "is_active"),
        select_related=("organization",), order_by=("name",), description="Manage websites, documents, FAQs and service catalogues used by AI.",
    ),
    "services": ResourceDefinition(
        key="services", label="Service offerings", singular="Service offering", icon="🧩", model=ServiceOffering,
        columns=(("organization", "Organization"), ("name", "Service"), ("category", "Category"), ("price_from", "Price from"), ("is_active", "Active")),
        search_fields=("name", "slug", "category", "organization__name", "description"),
        form_fields=("organization", "name", "slug", "short_description", "description", "category", "price_from", "currency", "duration_minutes", "booking_url", "metadata", "is_active"),
        select_related=("organization",), order_by=("name",), description="Manage services that can be discovered and booked from virtual tours.",
    ),
    "vision-analyses": ResourceDefinition(
        key="vision-analyses", label="Vision analyses", singular="Vision analysis", icon="👁️", model=VisionAnalysis,
        columns=(("organization", "Organization"), ("scene", "Scene"), ("status", "Status"), ("scene_type", "Scene type"), ("confidence", "Confidence"), ("created_at", "Created")),
        search_fields=("organization__name", "scene__title", "scene_type", "summary", "status"),
        select_related=("organization", "scene"), readonly=True, allow_delete=False, description="Monitor YOLO, OCR and semantic vision processing.",
    ),
    "ai-runs": ResourceDefinition(
        key="ai-runs", label="AI runs", singular="AI run", icon="✨", model=AIRun,
        columns=(("organization", "Organization"), ("operation", "Operation"), ("provider", "Provider"), ("status", "Status"), ("latency_ms", "Latency"), ("created_at", "Created")),
        search_fields=("organization__name", "operation", "provider", "model_name", "status", "trace_id"),
        select_related=("organization",), readonly=True, allow_delete=False, description="Monitor provider usage, latency, cost and failures.",
    ),
    "discovery-searches": ResourceDefinition(
        key="discovery-searches", label="Discovery searches", singular="Discovery search", icon="🔎", model=DiscoverySearchLog,
        columns=(("query", "Query"), ("result_count", "Results"), ("selected_tour", "Selected tour"), ("created_at", "Created")),
        search_fields=("query", "selected_tour__title"), select_related=("selected_tour",), readonly=True, allow_delete=False,
        description="Review search demand without exposing redacted healthcare queries.",
    ),
    "analytics-events": ResourceDefinition(
        key="analytics-events", label="Traffic events", singular="Traffic event", icon="📈", model=AnalyticsEvent,
        columns=(("organization", "Organization"), ("event_type", "Event"), ("source", "Source"), ("session_id", "Session"), ("created_at", "Created")),
        search_fields=("organization__name", "event_type", "source", "session_id"), select_related=("organization", "place"), readonly=True, allow_delete=False,
        description="Review platform traffic and engagement events.",
    ),
}


def get_resource(key: str) -> ResourceDefinition | None:
    return RESOURCE_DEFINITIONS.get(key)
