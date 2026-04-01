from collections import Counter, defaultdict
from datetime import date

from .models import ContentItem, UserInteraction


class RecommendationService:
    def __init__(self, profile):
        self.profile = profile
        self.liked_ids = set(
            UserInteraction.objects.filter(profile=profile, action="liked").values_list("content_id", flat=True)
        )
        self.saved_ids = set(
            UserInteraction.objects.filter(profile=profile, action="saved").values_list("content_id", flat=True)
        )
        self.disliked_ids = set(
            UserInteraction.objects.filter(profile=profile, action="disliked").values_list("content_id", flat=True)
        )
        self.viewed_ids = set(
            UserInteraction.objects.filter(profile=profile, action="viewed").values_list("content_id", flat=True)
        )
        liked_items = ContentItem.objects.filter(id__in=self.liked_ids | self.saved_ids)
        self.affinity_genres = Counter(liked_items.values_list("genre", flat=True))
        self.affinity_domains = Counter(liked_items.values_list("domain", flat=True))
        self.affinity_tags = Counter()
        for item in liked_items:
            self.affinity_tags.update(item.tag_list())

    def score_item(self, item):
        score = (item.popularity_score * 0.35) + (item.quality_score * 0.4)
        reasons = []

        if item.domain in self.profile.domain_list():
            score += 15
            reasons.append("matches a preferred format")

        if item.genre in self.profile.genre_list():
            score += 18
            reasons.append("fits your favorite genre")

        if self.profile.current_mood and self.profile.current_mood in item.mood_list():
            score += 12
            reasons.append("matches your current mood")

        if self.affinity_genres.get(item.genre):
            score += 10 + (self.affinity_genres[item.genre] * 2)
            reasons.append("similar to formats you already liked")

        if self.affinity_domains.get(item.domain):
            score += 4 + self.affinity_domains[item.domain]

        shared_tags = sum(self.affinity_tags.get(tag, 0) for tag in item.tag_list())
        if shared_tags:
            score += min(shared_tags * 3, 12)
            reasons.append("connected to themes from your history")

        if self.profile.time_budget == "quick" and any(token in item.duration_label.lower() for token in ["5", "8", "10", "12"]):
            score += 8
            reasons.append("works for a quick session")
        elif self.profile.time_budget == "deep" and any(token in item.duration_label.lower() for token in ["90", "120", "series", "daily"]):
            score += 8
            reasons.append("supports a deeper session")

        freshness_days = max((date.today() - item.published_at).days, 0)
        freshness_bonus = max(0, 12 - min(freshness_days, 30) * 0.4)
        score += freshness_bonus
        if freshness_bonus >= 8:
            reasons.append("fresh and timely")

        if item.id in self.liked_ids:
            score += 20
            reasons.append("you already liked this item")
        if item.id in self.saved_ids:
            score += 15
            reasons.append("you saved this for later")
        if item.id in self.viewed_ids:
            score -= 6
        if item.id in self.disliked_ids:
            score -= 40

        if self.profile.discovery_mode == "explorer" and item.domain not in self.profile.domain_list():
            score += 10
            reasons.append("adds cross-domain discovery")
        elif self.profile.discovery_mode == "comfort" and item.domain not in self.profile.domain_list():
            score -= 8

        return round(score, 1), reasons[:3]

    def recommend(self, limit=12):
        scored = []
        for item in ContentItem.objects.all():
            score, reasons = self.score_item(item)
            if score > 20:
                scored.append({"item": item, "score": score, "reasons": reasons})

        scored.sort(key=lambda entry: entry["score"], reverse=True)

        diversified = []
        domain_counts = defaultdict(int)
        for entry in scored:
            if domain_counts[entry["item"].domain] >= 3 and len(diversified) < limit:
                continue
            diversified.append(entry)
            domain_counts[entry["item"].domain] += 1
            if len(diversified) >= limit:
                break

        if len(diversified) < limit:
            seen_ids = {entry["item"].id for entry in diversified}
            for entry in scored:
                if entry["item"].id not in seen_ids:
                    diversified.append(entry)
                if len(diversified) >= limit:
                    break

        return diversified

    def domain_summary(self):
        liked = ContentItem.objects.filter(id__in=self.liked_ids)
        counts = Counter(liked.values_list("domain", flat=True))
        return counts
