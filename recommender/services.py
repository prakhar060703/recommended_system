from collections import Counter, defaultdict
from datetime import date
from math import log, sqrt

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
        self.all_items = list(ContentItem.objects.all())
        self.idf = self._build_idf()
        self.profile_vector = self._build_profile_vector()

    def _tokenize(self, *parts):
        blocked = {
            "the", "and", "for", "with", "from", "this", "that", "your", "have", "into", "about",
            "will", "more", "than", "what", "when", "where", "they", "them", "their", "over",
        }
        tokens = []
        for part in parts:
            if not part:
                continue
            cleaned = "".join(ch.lower() if ch.isalnum() or ch == " " else " " for ch in str(part))
            tokens.extend(word for word in cleaned.split() if len(word) > 2 and word not in blocked)
        return tokens

    def _item_tokens(self, item):
        return self._tokenize(
            item.title,
            item.creator,
            item.source,
            item.domain,
            item.genre,
            item.description,
            item.keyword_blob,
            item.ai_topics,
            item.ai_summary,
            item.ai_mood,
            item.cross_domain_tags,
            item.moods,
        )

    def _build_idf(self):
        doc_count = max(len(self.all_items), 1)
        doc_freq = Counter()
        for item in self.all_items:
            doc_freq.update(set(self._item_tokens(item)))
        return {token: log((1 + doc_count) / (1 + freq)) + 1.0 for token, freq in doc_freq.items()}

    def _vectorize_tokens(self, tokens):
        term_freq = Counter(tokens)
        if not term_freq:
            return {}
        total_terms = sum(term_freq.values())
        return {
            token: (count / total_terms) * self.idf.get(token, 1.0)
            for token, count in term_freq.items()
        }

    def _build_profile_vector(self):
        profile_tokens = self._tokenize(
            self.profile.favorite_domains,
            self.profile.favorite_genres,
            self.profile.current_mood,
        )
        for item in self.all_items:
            if item.id in self.liked_ids:
                profile_tokens.extend(self._item_tokens(item) * 3)
            elif item.id in self.saved_ids:
                profile_tokens.extend(self._item_tokens(item) * 2)
            elif item.id in self.viewed_ids:
                profile_tokens.extend(self._item_tokens(item))
        return self._vectorize_tokens(profile_tokens)

    def _cosine_similarity(self, left, right):
        if not left or not right:
            return 0.0
        overlap = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in overlap)
        left_norm = sqrt(sum(value * value for value in left.values()))
        right_norm = sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    def score_item(self, item):
        item_vector = self._vectorize_tokens(self._item_tokens(item))
        similarity = self._cosine_similarity(self.profile_vector, item_vector)
        score = (
            (item.recommendation_score * 0.42)
            + (item.quality_score * 0.16)
            + (item.popularity_score * 0.08)
            + (similarity * 100 * 0.34)
        )
        reasons = []

        interaction_volume = len(self.liked_ids) + len(self.saved_ids) + len(self.viewed_ids)
        profile_weight = 1.0 if interaction_volume < 4 else 0.65

        if similarity > 0.18:
            score += similarity * 22
            reasons.append("strong content similarity")
        elif similarity > 0.1:
            reasons.append("good topical match")

        if item.domain in self.profile.domain_list():
            score += 9 * profile_weight
            reasons.append("matches a preferred format")

        if item.genre in self.profile.genre_list():
            score += 11 * profile_weight
            reasons.append("fits your favorite genre")

        matching_keywords = len(set(item.keyword_list()) & set(self.profile.genre_list() + self.profile.domain_list()))
        if matching_keywords:
            score += matching_keywords * 5
            reasons.append("aligned with your interest keywords")

        if self.profile.current_mood and self.profile.current_mood in item.mood_list():
            score += 7 * profile_weight
            reasons.append("matches your current mood")

        if self.profile.current_mood and item.ai_mood and self.profile.current_mood == item.ai_mood:
            score += 6
            reasons.append("ai mood match")

        if self.affinity_genres.get(item.genre):
            score += 10 + (self.affinity_genres[item.genre] * 2)
            reasons.append("similar to formats you already liked")

        if self.affinity_domains.get(item.domain):
            score += 4 + self.affinity_domains[item.domain]

        shared_tags = sum(self.affinity_tags.get(tag, 0) for tag in item.tag_list())
        if shared_tags:
            score += min(shared_tags * 3, 12)
            reasons.append("connected to themes from your history")

        score += min(item.provider_rank and max(0, 12 - item.provider_rank) or 0, 10)

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
            score += 6 * profile_weight
            reasons.append("adds cross-domain discovery")
        elif self.profile.discovery_mode == "comfort" and item.domain not in self.profile.domain_list():
            score -= 5 * profile_weight

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
