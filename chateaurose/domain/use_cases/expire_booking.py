from datetime import timedelta

from chateaurose.domain.entities.booking import BookingRequest
SUBMITTED = "SUBMITTED"
PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
AWAITING_ALTERNATIVE_PROVIDER = "AWAITING_ALTERNATIVE_PROVIDER"
WAITING_PROVIDER_ASSIGNMENT = "WAITING_PROVIDER_ASSIGNMENT"
CANCELLED = "CANCELLED"
EXPIRATION_DELAY = timedelta(hours=72)


def execute(
    *,
    booking_id: str,
    now,
    booking_repository,
    payment_gateway,
    notifier,
    operations_email: str | None = None,
) -> BookingRequest:
    booking = booking_repository.get(booking_id)

    if booking.status in (CANCELLED,):
        return booking

    reference_time = (booking.alternative_requested_at or booking.updated_at or booking.created_at) if booking.status == AWAITING_ALTERNATIVE_PROVIDER else booking.created_at
    if booking.status in (SUBMITTED, PENDING_CLIENT_VALIDATION, AWAITING_ALTERNATIVE_PROVIDER, WAITING_PROVIDER_ASSIGNMENT) and now - reference_time >= EXPIRATION_DELAY:
        expired_while_finding_alternative = booking.status == AWAITING_ALTERNATIVE_PROVIDER
        booking.status = CANCELLED
        booking.updated_at = now
        if booking.payment_auth_id:
            payment_gateway.release_auth(booking.payment_auth_id)
        booking.payment_status = "RELEASED" if booking.amount_due_now_cents > 0 else "WAIVED"
        euros = booking.estimated_price_cents / 100
        formatted_price = f"{euros:.2f}".replace(".", ",")
        formatted_price = f"{formatted_price} €"
        effective_date = booking.proposed_date or booking.desired_date
        notifier.notify(
            booking.provider_id,
            "Demande expirée",
            "\n".join(
                [
                    "Bonjour,",
                    "",
                    "La recherche d'alternative a expiré." if expired_while_finding_alternative else "La demande a expiré faute de confirmation.",
                    "Récapitulatif :",
                    f"- Date : {effective_date}",
                    f"- Lieu : {booking.location}",
                    f"- Tarif : {formatted_price}",
                    "",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        )
        notifier.notify(
            booking.client_contact["email"],
            "Demande expirée",
            "\n".join(
                [
                    f"Bonjour {booking.client_contact['name']},",
                    "",
                    "Nous n'avons pas trouvé d'alternative compatible dans le délai prévu." if expired_while_finding_alternative else "La demande a expiré faute de confirmation.",
                    "Récapitulatif :",
                    f"- Date : {effective_date}",
                    f"- Lieu : {booking.location}",
                    f"- Tarif : {formatted_price}",
                    "",
                    "Ton empreinte bancaire a été libérée. Si tu veux, tu peux déposer une nouvelle demande." if expired_while_finding_alternative else "Si tu veux, tu peux déposer une nouvelle demande.",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        )
        if operations_email:
            notifier.notify(
                operations_email,
                f"Demande expirée · {booking.id}",
                "\n".join(
                    [
                        "Une demande a expiré et l'empreinte bancaire a été libérée.",
                        f"- ID demande : {booking.id}",
                        f"- Cliente : {booking.client_contact['name']} ({booking.client_contact['email']})",
                        f"- Date : {effective_date}",
                        f"- Lieu : {booking.location}",
                        f"- Tarif : {formatted_price}",
                        f"- Statut précédent : {'alternative en recherche' if expired_while_finding_alternative else 'en attente'}",
                    ]
                ),
                reply_to=booking.client_contact["email"],
            )
        booking_repository.update(booking)
    return booking
