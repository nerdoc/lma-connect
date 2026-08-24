from django.contrib import admin

from .models import (
    EventSurvey,
    SurveyAnswer,
    SurveyChoice,
    SurveyQuestion,
    SurveyResponse,
)


class SurveyChoiceInline(admin.TabularInline):
    model = SurveyChoice
    extra = 2
    fields = ("order", "text", "text_de", "value")


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 1
    fields = ("order", "type", "text", "text_de", "is_required",
              "likert_min_label", "likert_max_label")
    show_change_link = True  # help texts, DE Likert labels and choices live on the question page


@admin.register(EventSurvey)
class EventSurveyAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "is_published", "allow_anonymous", "opens_at", "closes_at")
    list_filter = ("event", "is_published")
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("event",)
    inlines = [SurveyQuestionInline]
    fieldsets = (
        (None, {"fields": ("event", "slug", "is_published", "allow_anonymous",
                           "opens_at", "closes_at")}),
        ("Texts (EN)", {"fields": ("title", "intro_text")}),
        ("Texts (DE)", {
            "fields": ("title_de", "intro_text_de"),
            "description": "Optional — empty fields fall back to the English text "
                           "for German-speaking visitors."}),
    )


@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ("order", "text", "type", "survey", "is_required")
    list_filter = ("survey__event", "type", "is_required")
    search_fields = ("text", "text_de")
    autocomplete_fields = ("survey",)
    inlines = [SurveyChoiceInline]
    fieldsets = (
        (None, {"fields": ("survey", "order", "type", "is_required")}),
        ("Texts (EN)", {"fields": ("text", "help_text",
                                   "likert_min_label", "likert_max_label")}),
        ("Texts (DE)", {
            "fields": ("text_de", "help_text_de",
                       "likert_min_label_de", "likert_max_label_de"),
            "description": "Optional — empty fields fall back to the English text "
                           "for German-speaking visitors."}),
    )


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ("survey", "user_label", "submitted_at")
    list_filter = ("survey__event", "survey")
    autocomplete_fields = ("survey", "user")
    search_fields = ("survey__title", "user__username", "user__email")
    readonly_fields = ("created_at",)

    def user_label(self, obj):
        return obj.user.username if obj.user else "anonym"
    user_label.short_description = "User"


@admin.register(SurveyChoice)
class SurveyChoiceAdmin(admin.ModelAdmin):
    list_display = ("text", "question", "order")
    list_filter = ("question__survey__event",)
    search_fields = ("text", "text_de", "value")
    autocomplete_fields = ("question",)
    fields = ("question", "order", "text", "text_de", "value")


@admin.register(SurveyAnswer)
class SurveyAnswerAdmin(admin.ModelAdmin):
    list_display = ("response", "question", "value_summary")
    list_filter = ("question__type",)
    autocomplete_fields = ("response", "question", "choice")

    def value_summary(self, obj):
        if obj.value_bool is not None:
            return "✓ Ja" if obj.value_bool else "✗ Nein"
        if obj.value_int is not None:
            return f"{obj.value_int} ★"
        if obj.choice:
            return obj.choice.text
        return obj.value_text[:60] if obj.value_text else "—"
    value_summary.short_description = "Wert"
