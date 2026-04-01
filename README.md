# ConvergeIQ

ConvergeIQ is a Django-based generalized recommendation platform that brings together videos, music, podcasts, movies, and news in one interface.

## Features

- Personalized dashboard with cross-domain recommendations
- Profile tuning for formats, genres, mood, time budget, and discovery style
- Explore page with search and filters
- Content detail page with recommendation reasoning
- Library page showing user feedback history
- Seeded sample content across all required domains

## Stack

- Python 3.10
- Django 4.2
- SQLite

## Run locally

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_content
python manage.py runserver
```

Open `http://127.0.0.1:8000/`

## Optional admin

```bash
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/`

## Product summary

This project addresses the combined recommendation system problem by using one user profile across multiple content formats. Instead of keeping recommendation logic trapped inside separate platforms, it creates a unified feed driven by shared signals such as mood, genre, preferred format, available time, and direct feedback.
