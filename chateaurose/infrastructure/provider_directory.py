from booking.models import Provider
from chateaurose.domain.exceptions import NotFound


class DjangoProviderDirectory:
    def get_provider_contact(self, provider_id: str):
        try:
            provider = Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist as exc:
            raise NotFound("Provider not found") from exc
        return {
            "name": provider.name,
            "email": provider.contact_email or "",
            "phone": provider.contact_phone or "",
            "salon_zone": provider.salon_zone or "",
            "salon_address": provider.salon_address or "",
            "deposit_percentage": provider.deposit_percentage,
        }
