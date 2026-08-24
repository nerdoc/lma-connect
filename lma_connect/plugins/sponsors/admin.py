from django.contrib import admin

from .models import (
    Sponsor,
    SponsorContact,
    SponsorDownload,
    SponsorImage,
    SponsorLink,
    SponsorTier,
)


@admin.register(SponsorTier)
class SponsorTierAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "price", "slot_count", "order")
    list_filter = ("event",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class SponsorImageInline(admin.TabularInline):
    model = SponsorImage
    extra = 1
    fields = ("image", "caption", "caption_en", "order")


class SponsorContactInline(admin.TabularInline):
    model = SponsorContact
    extra = 1
    fields = ("name", "role", "role_en", "expertise", "expertise_en",
              "email", "phone", "linkedin_url", "photo", "order")


class SponsorLinkInline(admin.TabularInline):
    model = SponsorLink
    extra = 1
    fields = ("type", "label", "label_en", "url", "description", "description_en", "order")


class SponsorDownloadInline(admin.TabularInline):
    model = SponsorDownload
    extra = 1
    fields = ("type", "title", "title_en", "description", "description_en", "file", "order")


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "tier", "is_published", "is_featured", "has_english",
                    "contract_signed_at", "paid_at")
    list_editable = ("is_featured",)
    list_filter = ("event", "tier", "is_published", "is_featured")
    search_fields = ("name", "contact_person", "contact_email")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("event", "tier")
    inlines = [SponsorImageInline, SponsorContactInline, SponsorLinkInline, SponsorDownloadInline]
    fieldsets = (
        ("Basis", {"fields": ("event", "tier", "name", "slug", "is_published", "order")}),
        ("Branding", {"fields": ("logo", "banner", "is_featured"),
                      "description": "'Headline sponsor' additionally places the logo on "
                                     "the welcome screen and in the home page header — "
                                     "meant for platinum-level sponsors and the like."}),
        ("Bio & Highlights (DE)", {"fields": ("bio_short", "bio_long", "highlights_md")}),
        ("Bio & Highlights (EN)", {
            "fields": ("bio_short_en", "bio_long_en", "highlights_md_en"),
            "description": "Optional — empty fields fall back for visitors reading "
                           "automatisch auf den deutschen Text zurück."}),
        ("Kontakt (legacy — neu: Inline 'Ansprechpersonen')", {
            "fields": ("website", "contact_email", "contact_person"),
            "classes": ("collapse",)}),
        ("Vor Ort", {"fields": ("booth_location", "booth_location_en", "booth_x", "booth_y")}),
        ("Vertrag (intern)", {"fields": ("contract_signed_at", "paid_at", "notes_internal"),
                              "classes": ("collapse",)}),
    )

    @admin.display(boolean=True, description="EN")
    def has_english(self, obj: Sponsor) -> bool:
        """A traffic light in the list: are the most visible texts translated?
        Shows the organizers at a glance where the translation is still
        missing."""
        return bool(obj.bio_short_en or obj.bio_long_en or obj.highlights_md_en)


@admin.register(SponsorContact)
class SponsorContactAdmin(admin.ModelAdmin):
    list_display = ("name", "sponsor", "role", "expertise", "email", "order")
    list_filter = ("sponsor__event",)
    search_fields = ("name", "expertise", "expertise_en", "email")
    autocomplete_fields = ("sponsor",)


@admin.register(SponsorImage)
class SponsorImageAdmin(admin.ModelAdmin):
    list_display = ("sponsor", "caption", "order")
    list_filter = ("sponsor__event",)
    autocomplete_fields = ("sponsor",)


@admin.register(SponsorLink)
class SponsorLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "sponsor", "type", "url", "order")
    list_filter = ("sponsor__event", "type")
    search_fields = ("label", "label_en", "url")
    autocomplete_fields = ("sponsor",)


@admin.register(SponsorDownload)
class SponsorDownloadAdmin(admin.ModelAdmin):
    list_display = ("title", "sponsor", "type", "file", "order")
    list_filter = ("sponsor__event", "type")
    search_fields = ("title", "title_en", "description", "description_en")
    autocomplete_fields = ("sponsor",)
