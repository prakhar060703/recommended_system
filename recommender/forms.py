from django import forms

from .models import UserProfile


DOMAIN_OPTIONS = [
    ("video", "Videos"),
    ("music", "Music"),
    ("podcast", "Podcasts"),
    ("movie", "Movies"),
    ("news", "News"),
]

GENRE_OPTIONS = [
    ("technology", "Technology"),
    ("business", "Business"),
    ("science", "Science"),
    ("productivity", "Productivity"),
    ("wellness", "Wellness"),
    ("culture", "Culture"),
    ("thriller", "Thriller"),
    ("documentary", "Documentary"),
    ("indie", "Indie"),
    ("learning", "Learning"),
]

MOOD_OPTIONS = [
    ("curious", "Curious"),
    ("focused", "Focused"),
    ("relaxed", "Relaxed"),
    ("inspired", "Inspired"),
    ("upbeat", "Upbeat"),
]


class ProfileForm(forms.ModelForm):
    favorite_domains = forms.MultipleChoiceField(
        choices=DOMAIN_OPTIONS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    favorite_genres = forms.MultipleChoiceField(
        choices=GENRE_OPTIONS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    current_mood = forms.ChoiceField(choices=[("", "Any mood")] + MOOD_OPTIONS, required=False)

    class Meta:
        model = UserProfile
        fields = ["name", "favorite_domains", "favorite_genres", "current_mood", "time_budget", "discovery_mode"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "What should we call you?"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["favorite_domains"] = self.instance.domain_list()
            self.initial["favorite_genres"] = self.instance.genre_list()

    def clean_favorite_domains(self):
        return ",".join(self.cleaned_data["favorite_domains"])

    def clean_favorite_genres(self):
        return ",".join(self.cleaned_data["favorite_genres"])
