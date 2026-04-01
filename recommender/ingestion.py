import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.conf import settings
from django.utils import timezone

from .groq_client import enrich_content_item, groq_available
from .models import ContentItem, SyncState


DOMAIN_THEME = {
    "music": "midnight",
    "video": "aurora",
    "news": "steel",
    "podcast": "copper",
    "movie": "ember",
}


def fetch_json(url, headers=None):
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url, headers=None):
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def extract_keywords(*parts):
    stopwords = {
        "the", "and", "for", "with", "from", "this", "that", "into", "your", "what", "about",
        "are", "was", "will", "have", "has", "new", "best", "top", "more", "than", "after",
    }
    tokens = []
    for part in parts:
        if not part:
            continue
        clean = "".join(ch.lower() if ch.isalnum() or ch == " " else " " for ch in str(part))
        tokens.extend(word for word in clean.split() if len(word) > 2 and word not in stopwords)
    unique = []
    for token in tokens:
        if token not in unique:
            unique.append(token)
    return unique[:8]


def build_score(like_count, view_count, save_count, freshness_bonus=0, quality_score=60):
    return round(
        (like_count * 0.35)
        + (save_count * 0.45)
        + (view_count * 0.0008)
        + (quality_score * 0.35)
        + freshness_bonus,
        2,
    )


class ContentCollector:
    def __init__(self):
        self.now = timezone.now()

    def collect(self):
        collected = []
        for loader in [
            self.fetch_gnews_news,
            self.fetch_apple_music,
            self.fetch_apple_videos,
            self.fetch_apple_podcasts,
            self.fetch_apple_movies,
        ]:
            try:
                collected.extend(loader())
            except (HTTPError, URLError, TimeoutError, ValueError):
                continue
        return collected

    def fetch_gnews_news(self):
        token = os.getenv("GNEWS_API_KEY")
        if not token:
            return []
        params = urlencode({"country": "in", "lang": "en", "max": 10, "token": token})
        data = fetch_json(f"https://gnews.io/api/v4/top-headlines?{params}")
        items = []
        for article in data.get("articles", []):
            keywords = extract_keywords(article.get("title"), article.get("description"))
            items.append({
                "provider": "gnews",
                "provider_content_id": article.get("url", ""),
                "domain": "news",
                "title": article.get("title", "Untitled"),
                "creator": (article.get("source") or {}).get("name", "Unknown"),
                "source": "GNews",
                "external_url": article.get("url", ""),
                "image_url": article.get("image", ""),
                "genre": keywords[0] if keywords else "news",
                "description": article.get("description") or article.get("content") or "Trending news story.",
                "published_at": (article.get("publishedAt") or str(self.now.date()))[:10],
                "duration_label": "Article",
                "keyword_blob": ",".join(keywords),
                "cross_domain_tags": ",".join(keywords),
                "provider_like_count": 0,
                "provider_view_count": 1000,
                "provider_save_count": 0,
                "quality_score": 72,
                "recommendation_score": build_score(0, 1000, 0, freshness_bonus=14, quality_score=72),
                "raw_payload": article,
                "card_theme": DOMAIN_THEME["news"],
            })
        return items

    def fetch_apple_search(self, term, entity, domain, source_label, limit=10):
        params = urlencode({
            "term": term,
            "country": "in",
            "media": "all",
            "entity": entity,
            "limit": limit,
        })
        data = fetch_json(f"https://itunes.apple.com/search?{params}")
        items = []
        for index, entry in enumerate(data.get("results", []), start=1):
            title = entry.get("trackName") or entry.get("collectionName") or entry.get("artistName") or "Untitled"
            creator = entry.get("artistName") or entry.get("sellerName") or "Unknown"
            description = entry.get("longDescription") or entry.get("shortDescription") or entry.get("description") or f"Popular {domain} result from Apple public catalog."
            genre = entry.get("primaryGenreName", domain).lower()
            keywords = extract_keywords(
                title,
                description,
                creator,
                entry.get("primaryGenreName"),
            )
            rank_factor = max(1, (limit + 1) - index)
            like_count = rank_factor * 220
            view_count = rank_factor * 4200
            save_count = rank_factor * 70
            external_url = entry.get("trackViewUrl") or entry.get("collectionViewUrl") or entry.get("artistViewUrl") or ""
            items.append({
                "provider": "apple-public",
                "provider_content_id": str(entry.get("trackId") or entry.get("collectionId") or f"{entity}-{index}-{title}"),
                "domain": domain,
                "title": title,
                "creator": creator,
                "source": source_label,
                "external_url": external_url,
                "image_url": entry.get("artworkUrl600") or entry.get("artworkUrl100") or "",
                "genre": keywords[0] if keywords else genre,
                "description": description[:500],
                "published_at": (entry.get("releaseDate") or str(self.now.date()))[:10],
                "duration_label": entry.get("contentAdvisoryRating") or entity.title(),
                "keyword_blob": ",".join(keywords),
                "cross_domain_tags": ",".join(keywords),
                "provider_like_count": like_count,
                "provider_view_count": view_count,
                "provider_save_count": save_count,
                "quality_score": 78,
                "recommendation_score": build_score(like_count, view_count, save_count, freshness_bonus=10, quality_score=78),
                "raw_payload": entry,
                "card_theme": DOMAIN_THEME[domain],
            })
        return items

    def fetch_apple_music(self):
        return self.fetch_apple_search("india top music", "song", "music", "Apple iTunes Search")

    def fetch_apple_videos(self):
        return self.fetch_apple_search("india popular music video", "musicVideo", "video", "Apple iTunes Search")

    def fetch_apple_podcasts(self):
        return self.fetch_apple_search("india top podcast", "podcast", "podcast", "Apple iTunes Search")

    def fetch_apple_movies(self):
        return self.fetch_apple_search("india popular movie", "movie", "movie", "Apple iTunes Search")


def persist_content(entries):
    now = timezone.now()
    snapshot = []
    use_groq = groq_available()
    for entry in entries:
        entry["fetched_at"] = now
        entry.setdefault("ai_summary", "")
        entry.setdefault("ai_topics", "")
        entry.setdefault("ai_mood", "")
        entry.setdefault("ai_recommendation_note", "")
        if use_groq:
            try:
                enriched = enrich_content_item(
                    {
                        "domain": entry.get("domain"),
                        "title": entry.get("title"),
                        "creator": entry.get("creator"),
                        "source": entry.get("source"),
                        "description": entry.get("description"),
                        "keywords": entry.get("keyword_blob"),
                    }
                )
                if enriched:
                    entry["ai_summary"] = enriched.get("summary", "")[:180]
                    topics = enriched.get("topics", [])
                    if isinstance(topics, list):
                        entry["ai_topics"] = ",".join(str(topic).strip().lower() for topic in topics if str(topic).strip())[:300]
                    entry["ai_mood"] = enriched.get("mood", "")[:80]
                    entry["ai_recommendation_note"] = enriched.get("recommendation_note", "")[:220]
                    if entry["ai_summary"]:
                        entry["description"] = entry["ai_summary"]
                    if entry["ai_topics"]:
                        merged_keywords = ",".join(filter(None, [entry.get("keyword_blob", ""), entry["ai_topics"]]))
                        entry["keyword_blob"] = ",".join(dict.fromkeys([piece.strip() for piece in merged_keywords.split(",") if piece.strip()]))[:300]
                        entry["cross_domain_tags"] = entry["keyword_blob"]
                    if entry["ai_mood"] and not entry.get("moods"):
                        entry["moods"] = entry["ai_mood"]
            except Exception:
                pass
        content, _ = ContentItem.objects.update_or_create(
            provider=entry["provider"],
            provider_content_id=entry["provider_content_id"],
            defaults=entry,
        )
        snapshot.append(
            {
                "id": content.id,
                "title": content.title,
                "author": content.creator,
                "platform": content.source,
                "keyword": content.keyword_list(),
                "ai_summary": content.ai_summary,
                "ai_topics": content.ai_topic_list(),
                "ai_mood": content.ai_mood,
                "like_count": content.provider_like_count,
                "view_count": content.provider_view_count,
                "save_count": content.provider_save_count,
                "score": content.recommendation_score,
                "rank": content.provider_rank,
                "domain": content.domain,
                "image_url": content.image_url,
                "external_url": content.external_url,
            }
        )

    assign_domain_ranks()
    purge_old_content()
    write_snapshot_file()
    state, _ = SyncState.objects.get_or_create(key="daily_content_refresh")
    state.last_run_at = now
    state.metadata = {"items_synced": len(entries)}
    state.save(update_fields=["last_run_at", "metadata"])
    return snapshot


def assign_domain_ranks():
    for domain, _ in ContentItem.DOMAIN_CHOICES:
        items = list(
            ContentItem.objects.filter(domain=domain).order_by("-recommendation_score", "-provider_view_count", "-published_at")
        )
        for index, item in enumerate(items, start=1):
            item.provider_rank = index
            item.is_featured = index <= 3
            item.save(update_fields=["provider_rank", "is_featured"])


def purge_old_content():
    cutoff = timezone.now() - timedelta(days=2)
    ContentItem.objects.filter(fetched_at__lt=cutoff).delete()


def write_snapshot_file():
    target = Path(settings.BASE_DIR) / "data"
    target.mkdir(exist_ok=True)
    rows = list(
        ContentItem.objects.values(
            "title",
            "creator",
            "source",
            "keyword_blob",
            "provider_like_count",
            "provider_view_count",
            "provider_save_count",
            "recommendation_score",
            "provider_rank",
            "domain",
            "image_url",
            "external_url",
        )
    )
    snapshot_path = target / "content_snapshot.json"
    snapshot_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def fetch_google_trends_topics(geo="IN", limit=6):
    """
    Uses the public Google Trends RSS feed. This is not a formal public JSON API,
    but it is a freely accessible Google Trends feed endpoint commonly used for
    daily trending searches.
    """
    url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"
    rss_text = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ElementTree.fromstring(rss_text)
    namespace = {
        "ht": "https://trends.google.com/trending/rss",
        "media": "http://search.yahoo.com/mrss/",
    }
    items = []
    for index, item in enumerate(root.findall("./channel/item")[:limit], start=1):
        picture = item.findtext("ht:picture", default="", namespaces=namespace)
        approx_traffic = item.findtext("ht:approx_traffic", default="", namespaces=namespace)
        title = item.findtext("title", default="Trending topic")
        link = item.findtext("link", default="")
        news_item = item.find("ht:news_item", namespaces=namespace)
        summary = ""
        if news_item is not None:
            summary = news_item.findtext("ht:news_item_snippet", default="", namespaces=namespace)
        items.append(
            {
                "name": title,
                "volume": approx_traffic or "Trending now",
                "pulse": summary or "Trending in Google searches right now",
                "image_url": picture,
                "link": link,
                "rank": index,
            }
        )
    return items
