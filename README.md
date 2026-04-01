# ConvergeIQ

ConvergeIQ is a unified recommendation platform built with Django that brings together music, videos, podcasts, movies, and news in one product. Instead of forcing users to jump across disconnected platforms, it creates a single discovery experience with domain-wise ranking, personalized recommendations, social-trend awareness, and AI-assisted enrichment.

## Short Description

ConvergeIQ solves the combined recommendation system problem by collecting content from multiple domains, normalizing it into one structure, ranking it, and then personalizing it using user interests, interaction history, lightweight machine learning, and optional Groq-based AI enrichment.

## Features

- Public home page with global recommendations for all visitors
- Login and signup flow for personalized recommendation access
- Lightweight signup followed by an interest-selection onboarding step
- Personalized home feed grouped into Music, Video, News, Podcast, and Movie sections
- Horizontal scrollable domain sections for easier browsing
- Explore page with search and domain/genre filtering
- Library page showing user activity history
- Detail page for each content item
- Redirect from detail page to the real source content
- Live news ingestion using `GNews`
- Public Apple search/catalog data used for music, videos, podcasts, and movies
- Free public Google Trends feed used for trending-topic discovery
- Local fallback seeded content when live providers are unavailable
- Daily refresh trigger on first request of the day
- Retention policy that keeps only the latest two days of ingested content
- Content snapshot export to `data/content_snapshot.json`
- Normalized content fields such as title, author, platform, keywords, likes, views, saves, score, rank, image, and external link
- Domain-wise ranking of content items
- Display of image, likes, views, saves, and rank on cards
- User profile preferences for domains, genres, mood, time budget, and discovery style
- Ability for users to update interests later
- Gradual preference adaptation so new interests do not instantly overpower old behavior
- Feedback loop with viewed, liked, saved, and disliked actions
- CPU-friendly content-based recommendation engine
- TF-IDF style tokenization and cosine-similarity style matching for personalization
- Recommendation scoring that blends provider rank, popularity, quality, AI enrichment, and user behavior
- Optional Groq enrichment for AI summary, AI topics, AI mood, and AI recommendation note
- Admin support through Django admin

## Stack

- Python 3.10
- Django 4.2
- SQLite
- HTML templates
- Custom CSS
- Lightweight local ML-style recommendation logic
- Optional Groq API enrichment

## API Setup

`GNEWS_API_KEY` is used for live news.
`GROQ_API_KEY` is optional and is used to enrich content with AI-generated summary, topics, mood, and recommendation note.

Put these in `.env`:

```env
GNEWS_API_KEY=your_key
GROQ_API_KEY=your_key
```

Notes:
- Music, videos, podcasts, and movies are fetched from Apple public data and do not need extra API keys.
- Trending social topics are fetched from a public Google Trends feed.
- If `GNEWS_API_KEY` is missing, the project still works with fallback content.
- If `GROQ_API_KEY` is missing, the project still works without AI enrichment.

## Design

The product was designed as a real-world unified recommendation layer instead of a single-platform recommender. The core idea is that people do not consume only one format. Someone interested in technology may want a news article, a podcast episode, a documentary, a music playlist for focus, and a video in the same session. So the product was designed around:

- one normalized content model for all domains
- one home feed that is easy to scan by domain
- a public-first experience that works immediately
- a user-specific layer that gets stronger after login
- a recommendation engine that combines content understanding and user behavior
- a lightweight architecture that can run locally on CPU

The UI was kept smooth and readable:

- large visual cards
- clear domain sections
- image-first presentation
- simple metrics display
- clean action buttons
- minimal clutter in recommendation cards

## How It Works

### 1. Content Collection

The platform fetches content from multiple sources:

- news from `GNews`
- music from Apple public search data
- videos from Apple public search data
- podcasts from Apple public search data
- movies from Apple public search data
- social trend topics from Google Trends public feed

Each fetched item is normalized into a single structure with fields like:

- title
- creator/author
- platform/source
- image
- keywords
- likes
- views
- saves
- rank
- recommendation score
- external URL

### 2. Data Retention

This project is designed for a hackathon-style live product demo, so it does not store a large historical dataset. Instead:

- fresh content is fetched daily
- only the latest two days of content are kept
- older content is deleted automatically

This keeps the database small, relevant, and easy to manage during development/demo use.

### 3. AI Enrichment

If `GROQ_API_KEY` is available, each content item is enriched after ingestion with:

- a short AI summary
- AI topic tags
- an AI mood label
- a short AI recommendation note

These enriched fields improve recommendation quality and help the system understand content more semantically.

### 4. Recommendation Engine

The recommendation engine is a lightweight CPU-friendly content-based model.

It works by:

- tokenizing content title, description, creator, genre, keywords, mood, and AI metadata
- building a profile representation from user interests and past interactions
- comparing items and user profile using similarity scoring
- blending that score with:
  - provider rank
  - provider engagement metrics
  - freshness
  - popularity
  - quality score
  - explicit user actions

This creates a hybrid recommendation system that is:

- personalized
- explainable internally
- lightweight enough to run locally
- practical for a hackathon or prototype product

### 5. User Personalization

Users influence recommendations in two ways:

- explicit preferences:
  - favorite domains
  - favorite genres
  - mood
  - time budget
  - discovery style
- implicit behavior:
  - viewed
  - liked
  - saved
  - disliked

Interest changes are handled gradually so the feed stays stable and realistic instead of changing too abruptly.

## Run Locally

From the project folder:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_content
python manage.py refresh_content
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

Notes:
- `seed_content` loads fallback content
- `refresh_content` fetches current content and updates the snapshot
- on the first request of the day, the app also tries to refresh content automatically

## Optional Admin

If you want to manage data through Django admin:

```bash
python manage.py createsuperuser
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/admin/
```
