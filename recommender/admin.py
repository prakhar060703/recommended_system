from django.contrib import admin

from .models import ContentItem, SyncState, UserInteraction, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "current_mood", "discovery_mode", "time_budget", "updated_at")
    search_fields = ("name", "favorite_domains", "favorite_genres")


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ("title", "domain", "provider", "source", "provider_rank", "recommendation_score", "published_at")
    list_filter = ("domain", "genre", "provider", "is_featured")
    search_fields = ("title", "creator", "source", "description", "keyword_blob")


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ("profile", "content", "action", "created_at")
    list_filter = ("action", "content__domain")


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ("key", "last_run_at")

# Register your models here.
