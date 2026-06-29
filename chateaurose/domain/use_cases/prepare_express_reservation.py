from dataclasses import dataclass
from urllib.parse import quote, urlencode

from chateaurose.domain.exceptions import NotFound, ValidationError
from chateaurose.domain.gateways.notifier import NotifierPort
from chateaurose.domain.repositories.express_reservation import ExpressReservationCatalog


@dataclass(frozen=True)
class ExpressReservationTarget:
    service_name: str
    sub_service_name: str
    reservation_url: str


def _normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValidationError("Entre une adresse email valide.")
    return normalized


def _choice_key(service_slug: str, sub_service_slug: str) -> str:
    return f"{service_slug}/{sub_service_slug}"


def build_choice_value(service_slug: str, sub_service_slug: str) -> str:
    return _choice_key(service_slug, sub_service_slug)


def list_grouped_choices(catalog: ExpressReservationCatalog) -> list[dict]:
    groups: dict[str, dict] = {}
    for choice in catalog.list_visible_sub_services():
        group = groups.setdefault(
            choice.service_slug,
            {"service_name": choice.service_name, "service_slug": choice.service_slug, "choices": []},
        )
        group["choices"].append(
            {
                "label": choice.sub_service_name,
                "value": build_choice_value(choice.service_slug, choice.sub_service_slug),
            }
        )
    return list(groups.values())


def execute(
    *,
    email: str,
    selected_choice: str,
    catalog: ExpressReservationCatalog,
    notifier: NotifierPort,
    base_url: str = "",
) -> ExpressReservationTarget:
    normalized_email = _normalize_email(email)
    selected_choice = (selected_choice or "").strip()
    choices = {
        _choice_key(choice.service_slug, choice.sub_service_slug): choice
        for choice in catalog.list_visible_sub_services()
    }
    choice = choices.get(selected_choice)
    if choice is None:
        raise NotFound("Cette prestation n'est pas disponible en réservation express.")

    relative_path = f"/services/{quote(choice.service_slug)}/sous-services/{quote(choice.sub_service_slug)}/"
    reservation_url = f"{base_url.rstrip('/')}{relative_path}?{urlencode({'prefill_email': normalized_email})}#service-request"
    notifier.notify(
        normalized_email,
        f"Ton lien de réservation Château Rose · {choice.sub_service_name}",
        "\n".join(
            [
                "Bonjour,",
                "",
                "Voici ton lien pour continuer ta réservation Château Rose :",
                reservation_url,
                "",
                "Ton email sera pré-rempli pour gagner du temps.",
                "À très vite,",
                "Château Rose",
            ]
        ),
    )
    return ExpressReservationTarget(
        service_name=choice.service_name,
        sub_service_name=choice.sub_service_name,
        reservation_url=reservation_url,
    )
