from collections import Counter

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import DOMAIN_OPTIONS, GENRE_OPTIONS, ProfileForm
from .models import ContentItem, UserInteraction, UserProfile
from .services import RecommendationService


def get_active_profile(request):
    profile_id = request.session.get("profile_id")
    if profile_id:
        profile = UserProfile.objects.filter(id=profile_id).first()
        if profile:
            return profile

    profile = UserProfile.objects.create(
        name="Guest Explorer",
        favorite_domains="video,music,podcast",
        favorite_genres="technology,learning,productivity",
        current_mood="curious",
        discovery_mode="balanced",
        time_budget="focused",
    )
    request.session["profile_id"] = profile.id
    return profile


def build_common_context(profile):
    service = RecommendationService(profile)
    recommendations = service.recommend(limit=10)
    interactions = UserInteraction.objects.filter(profile=profile).select_related("content")
    stats = Counter(interactions.values_list("action", flat=True))
    liked_items = [interaction.content for interaction in interactions if interaction.action == "liked"][:4]
    saved_items = [interaction.content for interaction in interactions if interaction.action == "saved"][:4]

    return {
        "profile": profile,
        "recommendations": recommendations,
        "stats": stats,
        "liked_items": liked_items,
        "saved_items": saved_items,
        "domain_distribution": service.domain_summary(),
        "domain_options": DOMAIN_OPTIONS,
        "genre_options": GENRE_OPTIONS,
    }


def dashboard(request):
    profile = get_active_profile(request)
    context = build_common_context(profile)
    context["featured_items"] = ContentItem.objects.filter(is_featured=True)[:5]
    context["trending_news"] = ContentItem.objects.filter(domain="news")[:3]
    return render(request, "recommender/dashboard.html", context)


def onboarding(request):
    profile = get_active_profile(request)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save()
            request.session["profile_id"] = profile.id
            messages.success(request, "Your recommendation profile has been updated.")
            return redirect("dashboard")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "recommender/onboarding.html", {"form": form, "profile": profile})


def explore(request):
    profile = get_active_profile(request)
    query = request.GET.get("q", "").strip()
    selected_domain = request.GET.get("domain", "").strip()
    selected_genre = request.GET.get("genre", "").strip()

    items = ContentItem.objects.all()
    if query:
        items = items.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(creator__icontains=query))
    if selected_domain:
        items = items.filter(domain=selected_domain)
    if selected_genre:
        items = items.filter(genre=selected_genre)

    service = RecommendationService(profile)
    scored_items = []
    for item in items:
        score, reasons = service.score_item(item)
        scored_items.append({"item": item, "score": score, "reasons": reasons})
    scored_items.sort(key=lambda entry: entry["score"], reverse=True)

    context = build_common_context(profile)
    context.update(
        {
            "scored_items": scored_items[:20],
            "query": query,
            "selected_domain": selected_domain,
            "selected_genre": selected_genre,
        }
    )
    return render(request, "recommender/explore.html", context)


def library(request):
    profile = get_active_profile(request)
    interactions = UserInteraction.objects.filter(profile=profile).select_related("content").order_by("-created_at")
    context = build_common_context(profile)
    context["interactions"] = interactions
    return render(request, "recommender/library.html", context)


def content_detail(request, content_id):
    profile = get_active_profile(request)
    content = get_object_or_404(ContentItem, id=content_id)
    UserInteraction.objects.get_or_create(profile=profile, content=content, action="viewed")
    service = RecommendationService(profile)
    score, reasons = service.score_item(content)
    related = [
        entry for entry in service.recommend(limit=6) if entry["item"].id != content.id and entry["item"].genre == content.genre
    ][:4]
    context = build_common_context(profile)
    context.update(
        {
            "content": content,
            "detail_score": score,
            "detail_reasons": reasons,
            "related_items": related,
        }
    )
    return render(request, "recommender/detail.html", context)


@require_POST
def interact(request, content_id, action):
    profile = get_active_profile(request)
    content = get_object_or_404(ContentItem, id=content_id)
    valid_actions = {"viewed", "liked", "saved", "disliked"}
    if action not in valid_actions:
        messages.error(request, "Unsupported action.")
        return redirect(request.META.get("HTTP_REFERER", "dashboard"))

    UserInteraction.objects.get_or_create(profile=profile, content=content, action=action)
    messages.success(request, f"{content.title} marked as {action}.")
    return redirect(request.META.get("HTTP_REFERER", "dashboard"))
