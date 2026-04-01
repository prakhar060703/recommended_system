from django.core.management import call_command
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .models import SyncState


class DailyContentRefreshMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            return self.get_response(request)

        try:
            state, _ = SyncState.objects.get_or_create(key="daily_content_refresh")
            today = timezone.localdate()
            last_date = timezone.localtime(state.last_run_at).date() if state.last_run_at else None
            if last_date != today:
                call_command("refresh_content", "--silent")
        except (OperationalError, ProgrammingError):
            pass

        return self.get_response(request)
