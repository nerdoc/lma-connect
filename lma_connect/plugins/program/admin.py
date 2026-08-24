from django.contrib import admin

from .models import (
    LivePoll,
    LivePollOption,
    LivePollResponse,
    Question,
    QuestionUpvote,
    Session,
    SessionChair,
    SessionRating,
    SessionSpeaker,
    Track,
)


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "color", "order")
    list_filter = ("event",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class SessionSpeakerInline(admin.TabularInline):
    model = SessionSpeaker
    extra = 1
    autocomplete_fields = ("speaker",)
    fields = ("speaker", "role", "order")


class SessionChairInline(admin.TabularInline):
    model = SessionChair
    extra = 1
    autocomplete_fields = ("user",)
    fields = ("user", "order")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "track", "type", "starts_at", "room", "is_published", "screen_source")
    list_filter = ("event", "track", "type", "is_published", "qa_enabled", "screen_source")
    search_fields = ("title", "summary")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("event", "track", "room", "screen_poll")
    inlines = [SessionChairInline, SessionSpeakerInline]
    fieldsets = (
        ("Basis", {"fields": ("event", "track", "room", "title", "slug", "summary", "type", "is_published")}),
        ("Zeit", {"fields": ("starts_at", "ends_at")}),
        ("Interaktion", {"fields": ("qa_enabled", "qa_moderated", "rating_enabled")}),
        ("Beamer / Room screen", {
            "fields": ("screen_source", "screen_poll"),
            "description": "Driven live by the chair from the chair panel. This is "
                           "for inspection and emergency correction only. 'Poll results' "
                           "projects the poll selected under 'Projected poll'.",
        }),
    )


@admin.register(SessionSpeaker)
class SessionSpeakerAdmin(admin.ModelAdmin):
    list_display = ("speaker", "session", "role", "order")
    list_filter = ("session__event", "role")
    autocomplete_fields = ("session", "speaker")


@admin.register(SessionChair)
class SessionChairAdmin(admin.ModelAdmin):
    list_display = ("user", "session", "order")
    list_filter = ("session__event",)
    search_fields = ("user__username", "user__first_name", "session__title")
    autocomplete_fields = ("session", "user")


# ─── Live Q&A ──────────────────────────────────────────

@admin.action(description="Ausgewählte Fragen freigeben")
def approve_questions(modeladmin, request, queryset):
    queryset.update(is_approved=True)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text_preview", "session", "asker_label", "is_starred", "is_approved",
                    "is_answered", "flagged_count", "created_at")
    list_filter = ("session__event", "is_starred", "is_approved", "is_answered")
    search_fields = ("text", "asker_display_name")
    autocomplete_fields = ("session", "asker", "added_by_chair")
    actions = [approve_questions]
    readonly_fields = ("flagged_count", "starred_at", "created_at", "updated_at")

    def text_preview(self, obj):
        return (obj.text[:80] + "…") if len(obj.text) > 80 else obj.text
    text_preview.short_description = "Frage"

    def asker_label(self, obj):
        if obj.added_by_chair:
            return f"chair: {obj.added_by_chair.username}"
        if obj.asker:
            return obj.asker.username
        return obj.asker_display_name or "anonym"
    asker_label.short_description = "Fragesteller"


@admin.register(QuestionUpvote)
class QuestionUpvoteAdmin(admin.ModelAdmin):
    list_display = ("question", "user", "created_at")
    autocomplete_fields = ("question", "user")


# ─── Session-Rating ────────────────────────────────────

@admin.register(SessionRating)
class SessionRatingAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "rating_overall", "rating_slides",
                    "rating_clarity", "rating_relevance", "is_anonymous", "created_at")
    list_filter = ("session__event", "rating_overall", "is_anonymous")
    search_fields = ("session__title", "comment")
    autocomplete_fields = ("session", "user")


# ─── Live-Polling ──────────────────────────────────────

class LivePollOptionInline(admin.TabularInline):
    model = LivePollOption
    extra = 2
    fields = ("text", "order")


@admin.register(LivePoll)
class LivePollAdmin(admin.ModelAdmin):
    list_display = ("question_text", "session", "type", "is_active", "is_results_public")
    list_filter = ("session__event", "type", "is_active")
    search_fields = ("question_text",)
    autocomplete_fields = ("session",)
    inlines = [LivePollOptionInline]


@admin.register(LivePollOption)
class LivePollOptionAdmin(admin.ModelAdmin):
    list_display = ("text", "poll", "order")
    list_filter = ("poll__session__event",)
    search_fields = ("text", "poll__question_text")
    autocomplete_fields = ("poll",)


@admin.register(LivePollResponse)
class LivePollResponseAdmin(admin.ModelAdmin):
    list_display = ("poll", "user", "option", "text_preview", "created_at")
    list_filter = ("poll__session__event",)
    autocomplete_fields = ("poll", "user", "option")

    def text_preview(self, obj):
        return obj.text_answer[:60] if obj.text_answer else "—"
