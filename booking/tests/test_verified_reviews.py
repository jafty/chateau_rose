from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, Provider, ReviewInvitation, Service, VerifiedReview
from chateaurose.domain.services.reviews import BookingReviewState, can_create_review, invitation_due, provider_review_badge, rating_label


class ReviewDomainTests(TestCase):
    def test_review_requires_confirmed_completed_unique_and_consent(self):
        now = timezone.now()
        self.assertEqual(can_create_review(booking_status="SUBMITTED", appointment_at=now, now=now, already_reviewed=False, consent_given=True)[1], "booking_not_confirmed")
        self.assertEqual(can_create_review(booking_status="CONFIRMED", appointment_at=now + timedelta(hours=1), now=now, already_reviewed=False, consent_given=True)[1], "appointment_not_completed")
        self.assertEqual(can_create_review(booking_status="CONFIRMED", appointment_at=now, now=now, already_reviewed=True, consent_given=True)[1], "duplicate_review")
        self.assertEqual(can_create_review(booking_status="CONFIRMED", appointment_at=now, now=now, already_reviewed=False, consent_given=False)[1], "missing_consent")
        self.assertTrue(can_create_review(booking_status="CONFIRMED", appointment_at=now, now=now, already_reviewed=False, consent_given=True)[0])

    def test_publication_badge_threshold_and_average(self):
        self.assertIsNone(provider_review_badge([5, 5, 5]))
        self.assertIsNone(provider_review_badge([5, 4, 4, 2]))
        self.assertEqual(provider_review_badge([5, 5, 4, 5]), {"label": "Excellent", "count": 4})

    def test_rating_labels_cover_all_review_form_choices(self):
        self.assertEqual([rating_label(i) for i in range(1, 6)], ["Décevant", "À améliorer", "Bien", "Très bien", "Excellent"])

    def test_invitation_and_reminder_rules(self):
        now = timezone.now()
        base = BookingReviewState(status="CONFIRMED", appointment_at=now - timedelta(days=2))
        self.assertEqual(invitation_due(base, now)[1], "first_request_due")
        self.assertEqual(invitation_due(BookingReviewState(status="CONFIRMED", appointment_at=now - timedelta(days=2), has_review=True), now)[1], "review_recorded")
        self.assertEqual(invitation_due(BookingReviewState(status="CONFIRMED", appointment_at=now - timedelta(days=2), has_incident_response=True), now)[1], "incident_recorded")
        self.assertEqual(invitation_due(BookingReviewState(status="CONFIRMED", appointment_at=now - timedelta(days=5), invitations_sent=1, last_invitation_sent_at=now - timedelta(days=3)), now)[1], "reminder_due")
        self.assertEqual(invitation_due(BookingReviewState(status="CONFIRMED", appointment_at=now - timedelta(days=10), invitations_sent=3, last_invitation_sent_at=now - timedelta(days=3)), now)[1], "max_reminders_reached")


@override_settings(STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class ReviewIntegrationTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Jannou")
        self.service = Service.objects.create(provider=self.provider, name="Vanilles", base_price_cents=4500)
        self.booking = Booking.objects.create(
            booking_id="BR-1", provider=self.provider, service=self.service, client_name="Aminata T.", client_email="a@example.com", location="Toulouse", desired_date=(timezone.now() - timedelta(days=2)).isoformat(), hair_length="court", meche=False, estimated_price_cents=4500, status=Booking.STATUS_CONFIRMED, created_at=timezone.now()
        )

    def test_secure_link_required_and_review_starts_pending(self):
        invitation = ReviewInvitation.objects.create(booking=self.booking)
        response = self.client.post(reverse("interface:leave_verified_review", args=[invitation.token]), {"rating": "5", "comment": "Super prestation", "consent_to_publish": "on"})
        self.assertContains(response, "Merci")
        review = VerifiedReview.objects.get(booking=self.booking)
        self.assertEqual(review.moderation_status, VerifiedReview.STATUS_PENDING)
        self.assertFalse(review.is_published)
        self.assertEqual(self.client.get("/avis/not-a-token/").status_code, 404)

    @patch("chateaurose.infrastructure.email_notifier.EmailNotifier.notify")
    def test_review_request_command_sends_once_and_uses_secure_link(self, notify):
        from django.core.management import call_command
        call_command("send_review_requests")
        invitation = ReviewInvitation.objects.get(booking=self.booking)
        self.assertEqual(invitation.sent_count, 1)
        body = notify.call_args.args[2]
        self.assertIn(str(invitation.token), body)
        notify.reset_mock()
        call_command("send_review_requests")
        notify.assert_not_called()
