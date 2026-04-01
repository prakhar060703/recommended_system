from collections import Counter

from django.contrib import messages
from django.contrib.auth import login, logout
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import DOMAIN_OPTIONS, GENRE_OPTIONS, InterestForm, LoginForm, ProfileForm, SignUpForm
from .ingestion import fetch_google_trends_topics
from .models import ContentItem, UserInteraction, UserProfile
from .services import RecommendationService


DOMAIN_ORDER = ["music", "video", "news", "podcast", "movie"]


def get_active_profile(request):
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={
                "name": request.user.first_name or request.user.username,
                "favorite_domains": "music,video,news",
                "favorite_genres": "technology,learning,indie",
                "current_mood": "curious",
                "discovery_mode": "balanced",
                "time_budget": "focused",
            },
        )
        if not profile.name:
            profile.name = request.user.first_name or request.user.username
            profile.save(update_fields=["name"])
        return profile
    return None


def profile_needs_onboarding(profile):
    return profile and not profile.favorite_domains and not profile.favorite_genres and not profile.current_mood


def build_common_context(profile):
    stats = Counter()
    liked_items = []
    saved_items = []
    recommendations = []
    domain_distribution = Counter()

    if profile:
        service = RecommendationService(profile)
        recommendations = service.recommend(limit=12)
        interactions = UserInteraction.objects.filter(profile=profile).select_related("content")
        stats = Counter(interactions.values_list("action", flat=True))
        liked_items = [interaction.content for interaction in interactions if interaction.action == "liked"][:4]
        saved_items = [interaction.content for interaction in interactions if interaction.action == "saved"][:4]
        domain_distribution = service.domain_summary()

    try:
        social_topics = fetch_google_trends_topics(limit=6)
    except Exception:
        trending_counter = Counter()
        for item in ContentItem.objects.all()[:40]:
            trending_counter.update(item.keyword_list())
        social_topics = [
            {
                "name": keyword.replace("-", " ").title(),
                "volume": f"{180000 - (index * 9000)} mentions",
                "pulse": "Emerging across today's cross-platform content mix",
                "image_url": "",
                "link": "",
                "rank": index + 1,
            }
            for index, (keyword, _) in enumerate(trending_counter.most_common(6))
        ]

    return {
        "profile": profile,
        "recommendations": recommendations,
        "stats": stats,
        "liked_items": liked_items,
        "saved_items": saved_items,
        "domain_distribution": domain_distribution,
        "domain_options": DOMAIN_OPTIONS,
        "genre_options": GENRE_OPTIONS,
        "social_topics": social_topics,
    }


def build_home_sections(profile):
    sections = []
    if profile:
        service = RecommendationService(profile)
        scored_items = []
        for item in ContentItem.objects.all():
            score, reasons = service.score_item(item)
            scored_items.append({"item": item, "score": score, "reasons": reasons})
        scored_items.sort(key=lambda entry: entry["score"], reverse=True)
    else:
        scored_items = [
            {
                "item": item,
                "score": item.recommendation_score or round((item.popularity_score * 0.55) + (item.quality_score * 0.45), 1),
                "reasons": ["popular across the platform"],
            }
            for item in ContentItem.objects.all().order_by("domain", "provider_rank", "-recommendation_score")
        ]

    for domain in DOMAIN_ORDER:
        items = [entry for entry in scored_items if entry["item"].domain == domain][:5]
        sections.append({"domain": domain, "label": dict(ContentItem.DOMAIN_CHOICES)[domain], "items": items})
    return sections


def dashboard(request):
    profile = get_active_profile(request)
    context = build_common_context(profile)
    context["home_sections"] = build_home_sections(profile)
    context["featured_items"] = ContentItem.objects.order_by("provider_rank", "-recommendation_score")[:5]
    return render(request, "recommender/dashboard.html", context)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.save()
            UserProfile.objects.create(
                user=user,
                name=user.username,
                favorite_domains="",
                favorite_genres="",
                current_mood="",
                time_budget="focused",
                discovery_mode="balanced",
            )
            login(request, user)
            messages.success(request, "Account created. Now tell us what you like so we can personalize your feed.")
            return redirect("onboarding")
    else:
        form = SignUpForm()

    return render(request, "recommender/signup.html", {"form": form, "profile": None})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            profile = get_active_profile(request)
            if profile_needs_onboarding(profile):
                messages.info(request, "Please tell us what you like to unlock your personalized feed.")
                return redirect("onboarding")
            messages.success(request, "Welcome back. Your personalized feed is ready.")
            return redirect("dashboard")
    else:
        form = LoginForm(request)
    return render(request, "recommender/login.html", {"form": form, "profile": None})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out. Global recommendations are shown again.")
    return redirect("dashboard")


def onboarding(request):
    profile = get_active_profile(request)
    if not profile:
        messages.info(request, "Create an account or log in to tune your recommendation profile.")
        return redirect("login")

    if request.method == "POST":
        form = InterestForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save()
            messages.success(request, "Your interests are saved. We will blend them gradually with your existing behavior.")
            return redirect("dashboard")
    else:
        form = InterestForm(instance=profile)

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

    if profile:
        service = RecommendationService(profile)
        scored_items = []
        for item in items:
            score, reasons = service.score_item(item)
            scored_items.append({"item": item, "score": score, "reasons": reasons})
        scored_items.sort(key=lambda entry: entry["score"], reverse=True)
    else:
        scored_items = [
            {
                "item": item,
                "score": item.recommendation_score or round((item.popularity_score * 0.55) + (item.quality_score * 0.45), 1),
                "reasons": ["popular across the platform"],
            }
            for item in items.order_by("provider_rank", "-recommendation_score", "-quality_score")
        ]

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
    if not profile:
        messages.info(request, "Log in to view your saved and liked recommendation history.")
        return redirect("login")

    interactions = UserInteraction.objects.filter(profile=profile).select_related("content").order_by("-created_at")
    context = build_common_context(profile)
    context["interactions"] = interactions
    return render(request, "recommender/library.html", context)


def content_detail(request, content_id):
    profile = get_active_profile(request)
    content = get_object_or_404(ContentItem, id=content_id)
    score = content.recommendation_score or round((content.popularity_score * 0.55) + (content.quality_score * 0.45), 1)
    reasons = ["popular across the platform", "strong engagement signal", "live provider ranking"]

    if profile:
        UserInteraction.objects.get_or_create(profile=profile, content=content, action="viewed")
        service = RecommendationService(profile)
        score, reasons = service.score_item(content)
        related = [
            entry for entry in service.recommend(limit=8) if entry["item"].id != content.id and entry["item"].genre == content.genre
        ][:4]
    else:
        related = [
            {"item": item, "score": item.recommendation_score or round((item.popularity_score * 0.55) + (item.quality_score * 0.45), 1)}
            for item in ContentItem.objects.filter(domain=content.domain).exclude(id=content.id).order_by("provider_rank")[:4]
        ]

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
    if not profile:
        messages.info(request, "Log in to save feedback and unlock personalized recommendations.")
        return redirect("login")

    content = get_object_or_404(ContentItem, id=content_id)
    valid_actions = {"viewed", "liked", "saved", "disliked"}
    if action not in valid_actions:
        messages.error(request, "Unsupported action.")
        return redirect(request.META.get("HTTP_REFERER", "dashboard"))

    UserInteraction.objects.get_or_create(profile=profile, content=content, action=action)
    messages.success(request, f"{content.title} marked as {action}.")
    return redirect(request.META.get("HTTP_REFERER", "dashboard"))
