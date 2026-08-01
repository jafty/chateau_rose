from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run every recurring email task used by the Railway scheduler."

    def handle(self, *args, **options):
        self.stdout.write("Running recap follow-ups...")
        call_command("send_recap_follow_ups", stdout=self.stdout, stderr=self.stderr)
        self.stdout.write("Running booking reminders...")
        call_command("send_reminders", stdout=self.stdout, stderr=self.stderr)
        self.stdout.write("Running review requests and follow-ups...")
        call_command("send_review_requests", stdout=self.stdout, stderr=self.stderr)
        self.stdout.write(self.style.SUCCESS("All scheduled tasks completed."))
