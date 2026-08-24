from django.contrib import admin

from .models import BoothChoice, BoothQuiz, PosterRating


class BoothChoiceInline(admin.TabularInline):
    model = BoothChoice
    extra = 3


@admin.register(BoothQuiz)
class BoothQuizAdmin(admin.ModelAdmin):
    list_display = ("sponsor", "question", "is_active")
    list_filter = ("is_active",)
    search_fields = ("sponsor__name", "question")
    inlines = [BoothChoiceInline]


@admin.register(PosterRating)
class PosterRatingAdmin(admin.ModelAdmin):
    list_display = ("abstract", "user", "stars", "created_at")
    list_filter = ("stars",)
    search_fields = ("abstract__title", "abstract__poster_id", "user__username")
    readonly_fields = ("created_at", "updated_at")
