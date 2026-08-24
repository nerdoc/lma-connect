from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import PersonProfile, Speaker


class SpeakerInline(admin.StackedInline):
    model = Speaker
    extra = 0
    fields = ("is_keynote", "talk_subjects", "affiliation", "intro", "chair_notes")


@admin.register(PersonProfile)
class PersonProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "affiliation", "position", "profile_public")
    list_filter = ("event", "profile_public")
    search_fields = ("user__username", "user__last_name", "user__first_name", "affiliation")
    autocomplete_fields = ("user", "event")
    inlines = [SpeakerInline]


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ("profile", "is_keynote", "talk_subjects")
    list_filter = ("is_keynote", "profile__event")
    search_fields = ("profile__user__last_name", "profile__user__first_name", "talk_subjects")
    autocomplete_fields = ("profile",)
    fieldsets = (
        (None, {"fields": ("profile", "is_keynote", "talk_subjects", "affiliation", "intro")}),
        (_("Chair only"), {"fields": ("chair_notes",),
                           "description": _("Visible only to the session chairs — "
                                            "never on public pages.")}),
    )
