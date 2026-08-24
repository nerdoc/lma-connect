from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import (
    Committee,
    CommitteeMembership,
    ConsentRecord,
    Event,
    EventContact,
    Floorplan,
    InfoBlock,
    LegalPage,
    Room,
    User,
)

# The Tabler icon webfont — the same file the frontend uses
# (templates/base.html), from static/vendor/ rather than a CDN. Loaded in the
# admin so the icon field can show what it describes: the name being typed is
# rendered right next to it. Without that preview "tools-kitchen-2" is blind
# guesswork and a typo only surfaces on the live page.
# A relative path, not an absolute one: Django's Media classes resolve it
# through the staticfiles storage, which is what makes hashed delivery work.
TABLER_ICONS_CSS = "vendor/tabler-icons/tabler-icons.min.css"
TABLER_ICONS_URL = "https://tabler.io/icons"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "first_name", "last_name", "institution",
                    "city", "country", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email",
                     "institution", "department", "city")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Affiliation (shown on every public list)", {
            "fields": ("department", "institution", "city",
                       "country", "country_iso")}),
    )


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    fields = ("name", "slug", "capacity", "floor", "order")
    prepopulated_fields = {"slug": ("name",)}


class CommitteeInline(admin.TabularInline):
    model = Committee
    extra = 0
    fields = ("name", "slug", "order")
    prepopulated_fields = {"slug": ("name",)}


class EventContactInline(admin.TabularInline):
    model = EventContact
    extra = 1
    fields = ("role", "name", "company", "email", "phone", "website", "order")


class FloorplanInline(admin.TabularInline):
    model = Floorplan
    extra = 0
    fields = ("title", "title_de", "file", "is_exhibition_floor", "order")
    verbose_name = "Floorplan"
    verbose_name_plural = "Floorplans (as many levels as you need)"


class IconPreviewMedia:
    """Icon preview plus a link to the icon gallery for every `icon` field.

    A mixin because both the inline and the standalone change page need the
    same help.
    """

    class Media:
        css = {"all": (TABLER_ICONS_CSS,)}
        js = ("core/admin_icon_preview.js",)


class InfoBlockInline(IconPreviewMedia, admin.StackedInline):
    model = InfoBlock
    extra = 0
    fields = (("title", "icon", "order", "is_published"), "body", "title_de", "body_de")
    verbose_name = "Info block"
    verbose_name_plural = "Info blocks (Info tab)"


class LegalPageInline(admin.StackedInline):
    model = LegalPage
    extra = 0
    fields = (("title", "slug", "order", "is_published"), "body", "title_de", "body_de")
    prepopulated_fields = {"slug": ("title",)}
    verbose_name = "Legal page"
    verbose_name_plural = "Legal pages (footer links, served at /legal/<slug>/)"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "start_date", "end_date", "city", "is_published")
    list_filter = ("is_published",)
    search_fields = ("name", "slug", "city", "venue_name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("organizing_secretary",)
    inlines = [RoomInline, CommitteeInline, EventContactInline,
               FloorplanInline, InfoBlockInline, LegalPageInline]
    fieldsets = (
        ("Basics", {"fields": ("name", "slug", "subtitle", "is_published")}),
        ("Date & timezone", {"fields": ("start_date", "end_date", "timezone_name")}),
        ("Venue", {"fields": ("venue_name", "address", "city", "postal_code",
                              "country", "country_iso", "lat", "lon")}),
        # Not collapsed and near the top: the social event gets edited at
        # short notice and was simply not findable folded away at the bottom.
        ("🍷 Social Event", {
            "fields": ("social_event_title",
                       "social_event_start", "social_event_end",
                       "social_event_venue_name", "social_event_address", "social_event_city",
                       "social_event_url",
                       "social_event_meeting_point", "social_event_meeting_time",
                       "social_event_info"),
            "description": "Separate evening/networking event with its own venue. Fill "
                           "in what you have — every part is optional. Shows up as its own "
                           "card on the Info tab (with formatted date, maps button, "
                           "website button, meeting point and a 'contact the secretary "
                           "to register' mail button) and drives the 'Registered for "
                           "social event' flag in the ops profile. Leave the title, start "
                           "and venue empty to hide the card entirely."}),
        ("Branding & images", {"fields": ("description", "homepage_url",
                                          "logo", "banner", "welcome_image"),
                               "description": "Floorplans are no longer fields here — "
                                              "upload as many levels as you need in the "
                                              "'Floorplans' inline at the bottom."}),
        ("Brand colours", {
            "fields": ("theme_color", "accent_color", "highlight_color",
                       "surface_color", "text_color"),
            "description": "These five colours drive the entire interface — buttons, "
                           "badges, links, the bottom navigation and the projection "
                           "screens. Six-digit hex including the '#'. Check the "
                           "contrast between text colour and page background before "
                           "the conference; everything else is derived automatically."}),
        ("Organizer", {"fields": ("organizer_name", "organizer_logo", "organizer_url")}),
        ("Footer", {
            "fields": ("footer_label", "copyright_holder", "copyright_year_start",
                       "footer_extra_md"),
            "description": "Legal pages are no longer fields here — maintain as many "
                           "as you need in the 'Legal pages' inline at the bottom. "
                           "Each published page gets a footer link."}),
        ("Quick-link contact", {"fields": ("organizing_secretary",),
                                "description": "Optional User account. For full contact "
                                               "details (company, phone, email, website) "
                                               "use the 'Event contacts' inline below."}),
        ("Info tab", {
            "fields": ("emergency_number",),
            "description": "All text sections of the Info tab live in the "
                           "'Info blocks' inline at the bottom of this page — travel, "
                           "sightseeing, WiFi, catering, whatever your event needs.",
            "classes": ("collapse",)}),
        ("Tab visibility", {
            "fields": ("tab_program_enabled", "tab_sponsors_enabled",
                       "tab_abstracts_enabled", "tab_info_enabled",
                       "tab_feedback_enabled"),
            "description": "Toggle which tabs appear in the bottom navigation. "
                           "Disable to hide a section for this event."}),
        ("🇩🇪 Translations (German)", {
            "fields": ("subtitle_de", "venue_name_de", "address_de", "description_de",
                       "footer_extra_md_de", "social_event_info_de"),
            "description": "Optional German translations. Empty fields fall back to the "
                           "primary (English) value. Filled fields are shown to users with "
                           "German as active language.",
            "classes": ("collapse",)}),
    )


@admin.register(InfoBlock)
class InfoBlockAdmin(IconPreviewMedia, admin.ModelAdmin):
    list_display = ("title", "event", "icon_preview", "order", "is_published")
    list_filter = ("event", "is_published")
    list_editable = ("order", "is_published")
    search_fields = ("title", "body")
    autocomplete_fields = ("event",)

    @admin.display(description="Icon")
    def icon_preview(self, obj: InfoBlock) -> str:
        """Icon and name in the list — a typo is visible without clicking."""
        if not obj.icon:
            return "—"
        return format_html('<i class="ti ti-{0}" style="font-size:1.3rem"></i>&nbsp;{0}',
                           obj.icon)


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "slug", "order", "is_published")
    list_filter = ("event", "is_published")
    list_editable = ("order", "is_published")
    search_fields = ("title", "slug", "body")
    autocomplete_fields = ("event",)
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Floorplan)
class FloorplanAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "is_exhibition_floor", "order")
    list_filter = ("event", "is_exhibition_floor")
    list_editable = ("is_exhibition_floor", "order")
    search_fields = ("title",)
    autocomplete_fields = ("event",)


@admin.register(EventContact)
class EventContactAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "company", "event", "email", "phone", "order")
    list_filter = ("event", "role")
    search_fields = ("name", "company", "email")
    autocomplete_fields = ("event",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "capacity", "floor", "order")
    list_filter = ("event",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class CommitteeMembershipInline(admin.TabularInline):
    model = CommitteeMembership
    extra = 1
    autocomplete_fields = ("user",)
    fields = ("user", "role", "affiliation", "order")


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "order")
    list_filter = ("event",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CommitteeMembershipInline]


@admin.register(CommitteeMembership)
class CommitteeMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "committee", "role", "order")
    list_filter = ("committee__event", "committee", "role")
    autocomplete_fields = ("user", "committee")
    search_fields = ("user__username", "user__last_name", "user__first_name")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "type", "granted_at", "withdrawn_at", "is_active")
    list_filter = ("event", "type", "withdrawn_at")
    autocomplete_fields = ("user", "event")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
