from django.contrib import admin

from .models import ContentItem, UserInteraction, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "current_mood", "discovery_mode", "time_budget", "updated_at")
    search_fields = ("name", "favorite_domains", "favorite_genres")


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ("title", "domain", "genre", "source", "popularity_score", "is_featured")
    list_filter = ("domain", "genre", "is_featured")
    search_fields = ("title", "creator", "source", "description")


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ("profile", "content", "action", "created_at")
    list_filter = ("action", "content__domain")

# Register your models here.
