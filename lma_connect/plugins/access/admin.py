from axes.admin import AccessAttemptAdmin, AccessFailureLogAdmin, AccessLogAdmin
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import AccessToken, LoginAttempt, LoginFailureLog, LoginLog


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ("token_short", "event", "category", "label", "user", "is_active",
                    "redeemed_at", "qr_link")
    list_filter = ("event", "category", "is_active", "redeemed_at")
    search_fields = ("token", "label", "user__username", "user__first_name")
    autocomplete_fields = ("event", "user")
    readonly_fields = ("token", "redeemed_at", "last_seen_at", "qr_link",
                       "created_at", "updated_at")
    fieldsets = (
        ("Token", {"fields": ("token", "qr_link", "event", "category", "label")}),
        ("Status", {"fields": ("is_active", "user", "redeemed_at", "last_seen_at")}),
        ("Notizen", {"fields": ("notes", "created_at", "updated_at")}),
    )

    def token_short(self, obj):
        return f"{obj.token[:8]}…"
    token_short.short_description = "Token"

    def qr_link(self, obj):
        if not obj.token:
            return "—"
        url = reverse("qr:image", kwargs={"path": f"t/{obj.token}/"})
        redeem = obj.get_redeem_url()
        return format_html(
            '<a href="{}" target="_blank">QR-Code</a> · <a href="{}" target="_blank"><code>{}</code></a>',
            url, redeem, redeem,
        )
    qr_link.short_description = "QR / Link"


# The axes models with their original admin classes, but under "Access" —
# see the comment next to the proxies in models.py. Read-only material for the
# organizers: who failed when, and who is locked out.
admin.site.register(LoginAttempt, AccessAttemptAdmin)
admin.site.register(LoginFailureLog, AccessFailureLogAdmin)
admin.site.register(LoginLog, AccessLogAdmin)
