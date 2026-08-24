from django.contrib import admin

from .models import Achievement, ScoreEntry, UserAchievement


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "icon_class", "order")
    search_fields = ("name", "key", "description")
    prepopulated_fields = {}


@admin.register(ScoreEntry)
class ScoreEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "action", "points", "dedup_key", "created_at")
    list_filter = ("event", "action")
    search_fields = ("user__username", "user__first_name", "dedup_key")
    autocomplete_fields = ("user", "event")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "achievement", "event", "awarded_at")
    list_filter = ("event", "achievement")
    search_fields = ("user__username", "user__first_name")
    autocomplete_fields = ("user", "event", "achievement")
    readonly_fields = ("awarded_at", "created_at", "updated_at")
