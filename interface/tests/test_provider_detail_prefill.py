from django.test import TestCase

from booking.models import Provider
from interface.models import ProviderBookingDraft
from interface.views import _is_checkout_ready, _prefill_data_from_draft


class ProviderDetailPrefillTests(TestCase):
    def setUp(self):
        self.provider = Provider.objects.create(name="Divine")

    def test_prefill_data_from_draft_token_merges_identity_fields(self):
        draft = ProviderBookingDraft.objects.create(
            provider=self.provider,
            client_name="Léa",
            client_email="lea@example.com",
            payload={
                "service_id": "12",
                "hair_length": "long",
                "desired_date": "2026-06-10T10:00",
            },
        )

        prefill = _prefill_data_from_draft(self.provider, str(draft.token))

        self.assertEqual(prefill["client_name"], "Léa")
        self.assertEqual(prefill["client_email"], "lea@example.com")
        self.assertEqual(prefill["service_id"], "12")
        self.assertEqual(prefill["draft_token"], str(draft.token))

    def test_prefill_data_from_draft_token_returns_empty_for_unknown_token(self):
        prefill = _prefill_data_from_draft(self.provider, "not-a-token")

        self.assertEqual(prefill, {})

    def test_is_checkout_ready_returns_true_only_with_required_fields(self):
        self.assertTrue(
            _is_checkout_ready(
                {
                    "service_id": "12",
                    "hair_length": "long",
                    "location_preference": "salon",
                    "location": "Toulouse Centre",
                    "desired_date": "2026-06-10T10:00",
                    "client_name": "Léa",
                    "client_email": "lea@example.com",
                }
            )
        )
        self.assertFalse(
            _is_checkout_ready(
                {
                    "service_id": "12",
                    "location_preference": "salon",
                    "location": "Toulouse Centre",
                }
            )
        )
