from django.contrib import admin, messages
from django.contrib.auth import get_user_model

from .models import (
    Abstract,
    AbstractAuthor,
    AbstractAward,
    AbstractCategory,
    AbstractReference,
    AbstractReview,
    AbstractStarVote,
    AbstractTag,
)


@admin.register(AbstractAward)
class AbstractAwardAdmin(admin.ModelAdmin):
    """The prizes an event hands out. Free-form per event — create as many as
    the jury decided on, and tick "audience choice" on the one the attendees
    vote for (at most one per event)."""

    list_display = ("name", "event", "is_audience_choice", "order", "winner_count")
    list_filter = ("event", "is_audience_choice")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def winner_count(self, obj):
        return obj.abstracts.count()
    winner_count.short_description = "# Winners"


@admin.register(AbstractCategory)
class AbstractCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "color", "order")
    list_filter = ("event",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(AbstractTag)
class AbstractTagAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "color", "abstract_count")
    list_filter = ("event",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def abstract_count(self, obj):
        return obj.abstracts.count()
    abstract_count.short_description = "# Abstracts"


class AbstractAuthorInline(admin.TabularInline):
    model = AbstractAuthor
    extra = 1
    autocomplete_fields = ("user",)
    fields = ("order", "full_name", "user", "email", "affiliation",
              "country", "country_iso", "orcid", "is_presenting", "is_corresponding")


class AbstractReferenceInline(admin.TabularInline):
    model = AbstractReference
    extra = 1
    fields = ("order", "citation_text", "doi", "url")


class AbstractReviewInline(admin.TabularInline):
    model = AbstractReview
    extra = 0
    autocomplete_fields = ("reviewer",)
    fields = ("reviewer", "score", "submitted_at", "comment")
    readonly_fields = ("submitted_at",)


@admin.register(Abstract)
class AbstractAdmin(admin.ModelAdmin):
    list_display = ("poster_id", "title", "event", "category", "type", "status",
                    "award", "is_published", "has_poster", "star_count", "review_summary")
    list_editable = ("is_published", "has_poster")
    list_filter = ("event", "category", "tags", "type", "status", "award",
                   "is_published", "has_poster")
    search_fields = ("title", "poster_id", "abstract_text", "keywords")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("event", "category", "submitted_by", "award")
    filter_horizontal = ("tags",)
    inlines = [AbstractAuthorInline, AbstractReferenceInline, AbstractReviewInline]
    actions = ["assign_reviewer_action"]
    fieldsets = (
        ("Identification", {"fields": ("event", "category", "tags", "type",
                                       "poster_id", "location", "is_published",
                                       "has_poster")}),
        ("Content", {"fields": ("title", "slug", "abstract_text", "keywords")}),
        ("PEER pre-review", {"fields": ("peer_review",), "classes": ("collapse",)}),
        ("Workflow", {"fields": ("status", "submitted_by", "submitted_at", "decision_notes")}),
        ("Award", {"fields": ("award", "award_note", "award_at")}),
    )

    def star_count(self, obj):
        return obj.star_votes.count()
    star_count.short_description = "★"

    def review_summary(self, obj):
        rs = obj.reviews.all()
        done = [r.score for r in rs if r.score is not None]
        if not rs:
            return "—"
        if not done:
            return f"0/{len(rs)}"
        avg = sum(done) / len(done)
        return f"{len(done)}/{len(rs)} · ⌀ {avg:.1f}"
    review_summary.short_description = "Reviews"

    @admin.action(description="Assign a reviewer (to all selected abstracts)")
    def assign_reviewer_action(self, request, queryset):
        User = get_user_model()
        username = request.POST.get("reviewer_username", "").strip()
        if not username:
            self.message_user(request, "Pass the reviewer's username in the URL as "
                                       "?reviewer_username=…", level=messages.WARNING)
            return
        try:
            reviewer = User.objects.get(username=username)
        except User.DoesNotExist:
            self.message_user(request, f"User '{username}' not found", level=messages.ERROR)
            return
        created = 0
        for abstract in queryset:
            _, was_created = AbstractReview.objects.get_or_create(
                abstract=abstract, reviewer=reviewer)
            if was_created:
                created += 1
        self.message_user(request, f"Created {created} new assignments for {reviewer.username}",
                          level=messages.SUCCESS)


@admin.register(AbstractAuthor)
class AbstractAuthorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "abstract", "country_iso", "is_presenting",
                    "is_corresponding", "order")
    list_filter = ("is_presenting", "is_corresponding", "abstract__event", "country_iso")
    search_fields = ("full_name", "email", "affiliation", "country")
    autocomplete_fields = ("abstract", "user")


@admin.register(AbstractReference)
class AbstractReferenceAdmin(admin.ModelAdmin):
    list_display = ("abstract", "order", "citation_preview", "doi")
    search_fields = ("citation_text", "doi")
    autocomplete_fields = ("abstract",)

    def citation_preview(self, obj):
        return (obj.citation_text[:80] + "…") if len(obj.citation_text) > 80 else obj.citation_text


@admin.register(AbstractReview)
class AbstractReviewAdmin(admin.ModelAdmin):
    list_display = ("abstract", "reviewer", "score", "submitted_at", "updated_at")
    list_filter = ("score", "reviewer", "abstract__event")
    search_fields = ("abstract__title", "abstract__poster_id", "reviewer__username")
    autocomplete_fields = ("abstract", "reviewer")
    readonly_fields = ("submitted_at", "updated_at")


@admin.register(AbstractStarVote)
class AbstractStarVoteAdmin(admin.ModelAdmin):
    """Read-only — a cast vote is final. A star moved after the fact in the
    admin would make the result impossible to follow; deleting remains
    available to correct abuse."""

    list_display = ("abstract", "user", "created_at")
    list_filter = ("abstract__event", "abstract__category")
    search_fields = ("abstract__title", "abstract__poster_id", "user__username")
    readonly_fields = ("abstract", "user", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
