from django.core.management.base import BaseCommand

from recommender.ingestion import ContentCollector, persist_content


class Command(BaseCommand):
    help = "Fetch live cross-domain content and keep only the latest two days."

    def add_arguments(self, parser):
        parser.add_argument("--silent", action="store_true")

    def handle(self, *args, **options):
        collector = ContentCollector()
        entries = collector.collect()
        if not entries:
            message = "No live content fetched. Configure API keys to ingest provider data."
            if not options["silent"]:
                self.stdout.write(self.style.WARNING(message))
            return

        snapshot = persist_content(entries)
        if not options["silent"]:
            self.stdout.write(self.style.SUCCESS(f"Refreshed {len(snapshot)} content items."))
