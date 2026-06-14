from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.test import TestCase, override_settings

from booking.admin import BookingAdmin
from booking.models import Booking, Provider, Service


class BookingAdminTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Diva")
        self.service = Service.objects.create(
            provider=self.provider,
            name="Tresses",
            slug="tresses",
            base_price_cents=5000,
        )
        self.booking = Booking.objects.create(
            booking_id="BK-TEST01",
            provider=self.provider,
            service=self.service,
            client_name="Alice",
            client_email="alice@example.com",
            location="Toulouse",
            location_preference="domicile",
            client_address="5 place du Capitole, Toulouse",
            desired_date="2026-01-01T10:00:00+00:00",
            hair_length="medium",
            general_adjustments=[],
            meche=False,
            current_hair_picture="bookings/current/current.jpg",
            inspiration_pictures=["bookings/inspiration/a.jpg", "bookings/inspiration/b.jpg"],
            free_text="",
            estimated_price_cents=8000,
            payment_auth_id="pi_123",
            status="SUBMITTED",
            created_at="2026-01-01T09:00:00+00:00",
        )
        self.model_admin = BookingAdmin(Booking, AdminSite())

    def test_inspiration_pictures_count_matches_payload(self):
        self.assertEqual(self.model_admin.inspiration_pictures_count(self.booking), 2)

    @override_settings(MEDIA_URL="/media/")
    def test_current_hair_picture_preview_displays_media_url(self):
        html = str(self.model_admin.current_hair_picture_preview(self.booking))

        self.assertIn('/media/bookings/current/current.jpg', html)
        self.assertIn("<img", html)

    @override_settings(MEDIA_URL="/media/")
    def test_inspiration_pictures_preview_displays_all_images(self):
        html = str(self.model_admin.inspiration_pictures_preview(self.booking))

        self.assertIn('/media/bookings/inspiration/a.jpg', html)
        self.assertIn('/media/bookings/inspiration/b.jpg', html)
        self.assertIn("Ouvrir l'image 1", html)
        self.assertIn("Ouvrir l'image 2", html)

    def test_assign_provider_view_uses_assignment_use_case(self):
        waiting = Booking.objects.create(
            booking_id="BK-GEN01",
            booking_kind=Booking.KIND_GENERIC,
            requested_service_label_snapshot="Tresses",
            client_name="Awa",
            client_email="awa@example.com",
            location="Toulouse",
            location_preference="domicile",
            desired_date="2026-01-02T10:00:00+00:00",
            hair_length="",
            general_adjustments=[],
            meche=False,
            current_hair_picture="",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=0,
            payment_auth_id="",
            payment_status=Booking.PAYMENT_STATUS_WAIVED,
            status=Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT,
            created_at="2026-01-01T09:00:00+00:00",
        )
        request = type("Request", (), {"POST": {"service_id": str(self.service.id)}, "GET": {}})()
        request._messages = type("Messages", (), {"add": lambda *args, **kwargs: None})()

        with patch("booking.admin.assign_provider_to_booking.execute") as execute_mock:
            execute_mock.return_value = None
            self.model_admin.assign_provider_view(request, str(waiting.pk))

        execute_mock.assert_called_once()
        self.assertEqual(execute_mock.call_args.kwargs["booking_id"], "BK-GEN01")
        self.assertEqual(execute_mock.call_args.kwargs["provider_id"], str(self.provider.id))
        self.assertEqual(execute_mock.call_args.kwargs["service_id"], str(self.service.id))

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import RequestFactory
from interface.models import MarketingService, MarketingSubService
from booking.models import ProviderZone, Zone


class BookingAdminAssignmentWorkflowTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.model_admin = BookingAdmin(Booking, self.site)
        self.factory = RequestFactory()
        self.marketing_service = MarketingService.objects.create(name="Braids", slug="braids")
        self.sub_service = MarketingSubService.objects.create(service=self.marketing_service, name="Vanilles", slug="vanilles")
        self.provider = Provider.objects.create(name="Diva", contact_email="diva@example.com")
        self.zone = Zone.objects.create(name="Toulouse", slug="toulouse")
        ProviderZone.objects.create(provider=self.provider, zone=self.zone)
        self.service = Service.objects.create(
            provider=self.provider,
            name="Vanilles",
            slug="vanilles",
            base_price_cents=10000,
            hair_length_adjustments={"standard": 0},
            general_adjustments={"extra-long": 2500},
            marketing_service=self.marketing_service,
        )
        self.service.marketing_sub_services.add(self.sub_service)
        self.booking = Booking.objects.create(
            booking_id="BK-ALT01",
            booking_kind=Booking.KIND_GENERIC,
            requested_marketing_service=self.marketing_service,
            requested_marketing_sub_service=self.sub_service,
            requested_service_label_snapshot="Braids · Vanilles",
            requested_options=["extra-long"],
            client_name="Awa",
            client_email="awa@example.com",
            location="Toulouse",
            location_preference="domicile",
            desired_date="2026-01-02T10:00:00+00:00",
            hair_length="standard",
            general_adjustments=["extra-long"],
            meche=False,
            current_hair_picture="",
            inspiration_pictures=[],
            free_text="",
            estimated_price_cents=900,
            provider_price_estimate_cents=None,
            chateau_rose_fee_cents=900,
            amount_due_now_cents=900,
            payment_auth_id="pi_keep",
            payment_status=Booking.PAYMENT_STATUS_AUTHORIZED,
            status=Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER,
            created_at="2026-01-01T09:00:00+00:00",
        )

    def _post(self, data):
        request = self.factory.post("/admin/booking/booking/assign/", data=data)
        setattr(request, "session", {})
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        return request

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", BREVO_API_KEY="")
    def test_admin_assignment_of_alternative_booking_succeeds_and_notifies(self):
        request = self._post({"provider": self.provider.id, "service": self.service.id})

        self.model_admin.assign_provider_view(request, str(self.booking.pk))

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.provider, self.provider)
        self.assertEqual(self.booking.service, self.service)
        self.assertEqual(self.booking.status, Booking.STATUS_SUBMITTED)
        self.assertEqual(self.booking.provider_price_estimate_cents, 12500)
        self.assertEqual(self.booking.estimated_price_cents, 13400)
        self.assertEqual(self.booking.payment_auth_id, "pi_keep")
        self.assertEqual(self.booking.amount_due_now_cents, 900)
        self.assertEqual(self.booking.chateau_rose_fee_cents, 900)
        self.assertEqual(self.booking.payment_status, Booking.PAYMENT_STATUS_AUTHORIZED)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Nouvelle demande attribuée", {message.subject for message in mail.outbox})
        self.assertIn("Ta demande a été transmise à une prestataire", {message.subject for message in mail.outbox})

    def test_incompatible_provider_service_fails_without_mutating_booking(self):
        other_sub = MarketingSubService.objects.create(service=self.marketing_service, name="Locks", slug="locks")
        self.service.marketing_sub_services.set([other_sub])
        request = self._post({"provider": self.provider.id, "service": self.service.id})

        self.model_admin.assign_provider_view(request, str(self.booking.pk))

        self.booking.refresh_from_db()
        self.assertIsNone(self.booking.provider)
        self.assertIsNone(self.booking.service)
        self.assertEqual(self.booking.status, Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER)
        self.assertIsNone(self.booking.provider_price_estimate_cents)

    def test_booking_without_current_hair_picture_can_be_saved_in_admin(self):
        self.booking.current_hair_picture = ""
        self.booking.full_clean()
        self.booking.save()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.current_hair_picture, "")
