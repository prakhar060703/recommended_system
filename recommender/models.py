from django.db import models


class UserProfile(models.Model):
    DISCOVERY_CHOICES = [
        ("balanced", "Balanced"),
        ("comfort", "Comfort picks"),
        ("explorer", "Explorer mode"),
    ]
    TIME_CHOICES = [
        ("quick", "Quick break"),
        ("focused", "Focused session"),
        ("deep", "Deep dive"),
    ]

    name = models.CharField(max_length=120, default="Guest")
    favorite_domains = models.CharField(max_length=200, blank=True)
    favorite_genres = models.CharField(max_length=300, blank=True)
    current_mood = models.CharField(max_length=80, blank=True)
    time_budget = models.CharField(max_length=20, choices=TIME_CHOICES, default="focused")
    discovery_mode = models.CharField(max_length=20, choices=DISCOVERY_CHOICES, default="balanced")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def domain_list(self):
        return [item.strip() for item in self.favorite_domains.split(",") if item.strip()]

    def genre_list(self):
        return [item.strip() for item in self.favorite_genres.split(",") if item.strip()]


class ContentItem(models.Model):
    DOMAIN_CHOICES = [
        ("video", "Video"),
        ("music", "Music"),
        ("podcast", "Podcast"),
        ("movie", "Movie"),
        ("news", "News"),
    ]

    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES)
    title = models.CharField(max_length=200)
    creator = models.CharField(max_length=150)
    source = models.CharField(max_length=120)
    genre = models.CharField(max_length=120)
    moods = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    duration_label = models.CharField(max_length=40, blank=True)
    release_year = models.PositiveIntegerField(default=2024)
    published_at = models.DateField()
    popularity_score = models.FloatField(default=50)
    quality_score = models.FloatField(default=50)
    cross_domain_tags = models.CharField(max_length=250, blank=True)
    card_theme = models.CharField(max_length=80, default="sunrise")
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_featured", "-popularity_score", "-published_at"]

    def __str__(self):
        return f"{self.title} ({self.domain})"

    def mood_list(self):
        return [item.strip() for item in self.moods.split(",") if item.strip()]

    def tag_list(self):
        return [item.strip() for item in self.cross_domain_tags.split(",") if item.strip()]


class UserInteraction(models.Model):
    ACTION_CHOICES = [
        ("viewed", "Viewed"),
        ("liked", "Liked"),
        ("saved", "Saved"),
        ("disliked", "Disliked"),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="interactions")
    content = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name="interactions")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "content", "action")

    def __str__(self):
        return f"{self.profile} - {self.action} - {self.content}"

# Create your models here.
