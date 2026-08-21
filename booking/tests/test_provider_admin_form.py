from django.test import TestCase

from booking.admin import ProviderAdminForm
from booking.models import Provider, ProviderMarketingService
from interface.models import MarketingService, MarketingSubService


class ProviderAdminFormMarketingSubServiceTests(TestCase):
    def setUp(self):
        self.service = MarketingService.objects.create(name="Tresses", slug="tresses")
        self.other_service = MarketingService.objects.create(name="Locks", slug="locks")
        self.sub_service = MarketingSubService.objects.create(
            service=self.service,
            name="Knotless braids",
            slug="knotless-braids",
        )
        self.other_sub_service = MarketingSubService.objects.create(
            service=self.other_service,
            name="Départ locks",
            slug="depart-locks",
        )

    def _form_data(self, provider, *, marketing_services=None, marketing_sub_services=None):
        data = {
            "name": provider.name,
            "description": provider.description,
            "seo_h1": provider.seo_h1,
            "availabilities": provider.availabilities,
            "additional_info": provider.additional_info,
            "contact_phone": provider.contact_phone,
            "contact_email": provider.contact_email,
            "preferred_contact_method": provider.preferred_contact_method,
            "post_confirmation_contact_instructions": provider.post_confirmation_contact_instructions,
            "deposit_cents": provider.deposit_cents,
            "deposit_percentage": provider.deposit_percentage,
            "service_fee_percentage": provider.service_fee_percentage,
            "salon_zone": provider.salon_zone,
            "salon_address": provider.salon_address,
            "provides_meche": "on",
            "location_mode": provider.location_mode,
            "homepage_order": provider.homepage_order,
            "is_visible_on_website": "on",
            "zones": [],
            "marketing_services": [str(service.pk) for service in (marketing_services or [])],
            "marketing_sub_services": [
                str(sub_service.pk) for sub_service in (marketing_sub_services or [])
            ],
        }
        if provider.categorized_services_enabled:
            data["categorized_services_enabled"] = "on"
        return data

    def test_existing_provider_initializes_selected_sub_services(self):
        provider = Provider.objects.create(name="Diva Admin")
        provider.marketing_sub_services.add(self.sub_service)

        form = ProviderAdminForm(instance=provider)

        self.assertIn(self.sub_service, form.fields["marketing_sub_services"].initial)

    def test_saving_provider_assigns_sub_services_from_provider_form(self):
        provider = Provider.objects.create(name="Diva Admin")
        form = ProviderAdminForm(
            data=self._form_data(
                provider,
                marketing_services=[],
                marketing_sub_services=[self.sub_service, self.other_sub_service],
            ),
            instance=provider,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertCountEqual(
            provider.marketing_sub_services.all(),
            [self.sub_service, self.other_sub_service],
        )

    def test_saving_sub_service_automatically_links_parent_marketing_service(self):
        provider = Provider.objects.create(name="Diva Admin")
        form = ProviderAdminForm(
            data=self._form_data(
                provider,
                marketing_services=[],
                marketing_sub_services=[self.sub_service],
            ),
            instance=provider,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertTrue(
            ProviderMarketingService.objects.filter(
                provider=provider,
                service=self.service,
            ).exists()
        )

    def test_saving_provider_replaces_sub_service_selection(self):
        provider = Provider.objects.create(name="Diva Admin")
        provider.marketing_sub_services.add(self.sub_service, self.other_sub_service)

        form = ProviderAdminForm(
            data=self._form_data(
                provider,
                marketing_services=[],
                marketing_sub_services=[self.other_sub_service],
            ),
            instance=provider,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertCountEqual(provider.marketing_sub_services.all(), [self.other_sub_service])
