from django.http import QueryDict
from django.test import TestCase

from booking.models import Provider
from interface.models import ProviderBookingDraft
from interface.views import _get_query_param, _is_checkout_ready, _prefill_data_from_draft


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
                    "desired_date": "2026-06-10T10:00",
                    "client_name": "Léa",
                    "client_email": "lea@example.com",
                }
            )
        )
        self.assertTrue(
            _is_checkout_ready(
                {
                    "service_id": "12",
                    "hair_length": "long",
                    "location_preference": "domicile",
                    "location": "Toulouse Centre",
                    "client_address": "12 rue des fleurs",
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
                }
            )
        )
        self.assertFalse(
            _is_checkout_ready(
                {
                    "service_id": "12",
                    "hair_length": "long",
                    "location_preference": "domicile",
                    "location": "Toulouse Centre",
                    "desired_date": "2026-06-10T10:00",
                    "client_name": "Léa",
                    "client_email": "lea@example.com",
                }
            )
        )

    def test_prefill_normalizes_home_location_preference(self):
        draft = ProviderBookingDraft.objects.create(
            provider=self.provider,
            client_name="Léa",
            client_email="lea@example.com",
            payload={
                "service_id": "12",
                "hair_length": "long",
                "location_preference": "home",
                "desired_date": "2026-06-10T10:00",
            },
        )

        prefill = _prefill_data_from_draft(self.provider, str(draft.token))
        self.assertEqual(prefill["location_preference"], "domicile")

    def test_get_query_param_accepts_keys_with_leading_spaces(self):
        querydict = QueryDict("%20draft_token=f0c54969-87df-4123-99fa-11cee78c29d9&checkout=1")
        request = type("Req", (), {"GET": querydict})()

        self.assertEqual(
            _get_query_param(request, "draft_token"),
            "f0c54969-87df-4123-99fa-11cee78c29d9",
        )
        self.assertEqual(_get_query_param(request, "checkout"), "1")
