from datetime import date
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import models

from interface.validators import validate_absolute_or_root_relative_url
from interface.services.image_processing import compress_image_field


def _should_compress_image(instance: models.Model, field_name: str) -> bool:
    image_field = getattr(instance, field_name)
    if not image_field:
        return False
    if not instance.pk:
        return True
    try:
        previous = type(instance).objects.get(pk=instance.pk)
    except type(instance).DoesNotExist:
        return True
    previous_field = getattr(previous, field_name)
    if not previous_field:
        return True
    return image_field.name != previous_field.name


class ProviderQuerySet(models.QuerySet):
    def visible_on_website(self):
        return self.filter(is_visible_on_website=True)


class ProviderManager(models.Manager):
    def get_queryset(self):
        return ProviderQuerySet(self.model, using=self._db)

    def visible_on_website(self):
        return self.get_queryset().visible_on_website()


class Provider(models.Model):
    CONTACT_METHOD_CHATEAU_ROSE = "CHATEAU_ROSE"
    CONTACT_METHOD_EMAIL = "EMAIL"
    CONTACT_METHOD_PHONE = "PHONE"
    CONTACT_METHOD_WHATSAPP = "WHATSAPP"
    CONTACT_METHOD_CUSTOM = "CUSTOM"
    CONTACT_METHOD_CHOICES = (
        (CONTACT_METHOD_CHATEAU_ROSE, "Via Château Rose"),
        (CONTACT_METHOD_EMAIL, "Email"),
        (CONTACT_METHOD_PHONE, "Téléphone"),
        (CONTACT_METHOD_WHATSAPP, "WhatsApp"),
        (CONTACT_METHOD_CUSTOM, "Instructions personnalisées"),
    )
    LOCATION_MODE_SALON_ONLY = "salon_only"
    LOCATION_MODE_CLIENT_HOME_ONLY = "client_home_only"
    LOCATION_MODE_HYBRID = "hybrid"
    LOCATION_MODE_CHOICES = (
        (LOCATION_MODE_SALON_ONLY, "Salon uniquement"),
        (LOCATION_MODE_CLIENT_HOME_ONLY, "À domicile uniquement"),
        (LOCATION_MODE_HYBRID, "Salon ou domicile"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    seo_h1 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Texte H1 affiché sur la page prestataire à la place du prénom si renseigné.",
    )
    availabilities = models.TextField(
        blank=True,
        help_text="Disponibilités proposées pour la clientèle.",
    )
    additional_info = models.TextField(
        blank=True,
        help_text="Règles, conditions, informations complémentaires.",
    )
    contact_phone = models.CharField(max_length=64, blank=True)
    contact_email = models.EmailField(blank=True)
    preferred_contact_method = models.CharField(
        max_length=16,
        choices=CONTACT_METHOD_CHOICES,
        default=CONTACT_METHOD_CHATEAU_ROSE,
        help_text="Moyen de contact communiqué à la clientèle uniquement après confirmation.",
    )
    post_confirmation_contact_instructions = models.TextField(
        blank=True,
        help_text="Instructions complémentaires communiquées uniquement après confirmation.",
    )
    deposit_cents = models.IntegerField(
        default=2000,
        help_text="Montant fixe de l'acompte en centimes.",
    )
    deposit_percentage = models.PositiveSmallIntegerField(
        default=30,
        help_text="Pourcentage de l'estimation utilisé pour calculer l'acompte.",
    )
    service_fee_percentage = models.PositiveSmallIntegerField(
        default=15,
        help_text="Pourcentage de frais de service ajouté au prix des prestations.",
    )
    pending_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    salon_zone = models.CharField(
        max_length=255,
        blank=True,
        help_text="Indique la zone ou le quartier où tu reçois au salon.",
    )
    salon_address = models.TextField(
        blank=True,
        help_text="Adresse complète du salon (communiquée après confirmation).",
    )
    provides_meche = models.BooleanField(
        default=True,
        help_text="Active si la prestataire fournit les mèches.",
    )
    profile_image = models.ImageField(
        upload_to="providers/profile/", blank=True, null=True
    )
    profile_image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    location_mode = models.CharField(
        max_length=32,
        choices=LOCATION_MODE_CHOICES,
        default=LOCATION_MODE_HYBRID,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_profile",
    )
    zones = models.ManyToManyField(
        "Zone",
        through="ProviderZone",
        related_name="providers",
        blank=True,
    )
    marketing_services = models.ManyToManyField(
        "interface.MarketingService",
        through="ProviderMarketingService",
        related_name="providers",
        blank=True,
    )
    categorized_services_enabled = models.BooleanField(
        default=False,
        help_text="Active la présentation des services par catégories sur la page prestataire.",
    )
    homepage_order = models.PositiveIntegerField(
        default=0,
        help_text="Ordre d'affichage sur la page d'accueil (plus petit = affiché en premier).",
    )
    is_visible_on_website = models.BooleanField(
        default=True,
        help_text=(
            "Décoche pour masquer ce profil des listes publiques du site "
            "(accueil, pages service, listes de prestataires)."
        ),
    )

    objects = ProviderManager()

    def __str__(self):
        return self.name

    @property
    def display_h1(self):
        return (self.seo_h1 or "").strip() or self.name

    @property
    def resolved_profile_image(self):
        if self.profile_image:
            return self.profile_image.url
        return self.profile_image_url or None

    @property
    def resolved_cover_image(self):
        photo = self.photos.filter(media_kind=ProviderPhoto.MEDIA_IMAGE).first()
        if photo and photo.resolved_url:
            return photo.resolved_url
        return self.resolved_profile_image

    @property
    def location_mode_label(self):
        return dict(self.LOCATION_MODE_CHOICES).get(self.location_mode, "")

    @property
    def review_badge(self):
        from chateaurose.domain.services.reviews import provider_review_badge

        ratings = list(
            self.verified_reviews.filter(
                moderation_status=VerifiedReview.STATUS_APPROVED,
                consent_to_publish=True,
                is_verified=True,
                rating__isnull=False,
            ).values_list("rating", flat=True)
        )
        return provider_review_badge(ratings)

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "profile_image"):
            compress_image_field(self.profile_image, max_px=320, quality=76)
        return super().save(*args, **kwargs)


class Zone(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, default="")

    def __str__(self):
        return self.name


class Service(models.Model):
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="services"
    )
    category = models.ForeignKey(
        "ServiceCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, default="", blank=True)
    image = models.ImageField(upload_to="providers/services/", blank=True, null=True)
    image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    base_price_cents = models.IntegerField()
    hair_length_adjustments = models.JSONField(default=dict, blank=True)
    type_adjustments = models.JSONField(default=dict, blank=True)
    general_adjustments = models.JSONField(default=dict, blank=True)
    meche_bonus_cents = models.IntegerField(default=0)
    at_home_bonus_cents = models.IntegerField(default=0)
    marketing_service = models.ForeignKey(
        "interface.MarketingService",
        on_delete=models.SET_NULL,
        related_name="provider_services",
        null=True,
        blank=True,
    )
    marketing_sub_services = models.ManyToManyField(
        "interface.MarketingSubService",
        related_name="provider_services",
        blank=True,
    )

    class Meta:
        unique_together = (("provider", "name"), ("provider", "slug"))

    def __str__(self):
        return f"{self.name} ({self.provider})"

    @property
    def resolved_image(self):
        if self.image:
            return self.image.url
        if self.image_url:
            return self.image_url
        return (
            self.provider.resolved_cover_image or self.provider.resolved_profile_image
        )

    def clean(self):
        super().clean()
        if self.category and self.category.provider_id != self.provider_id:
            raise ValidationError("La catégorie doit appartenir à la même prestataire.")

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "image"):
            compress_image_field(self.image, max_px=720, quality=80)
        return super().save(*args, **kwargs)


class ServiceCategory(models.Model):
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="service_categories",
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "name")
        unique_together = ("provider", "name")

    def __str__(self):
        return f"{self.name} ({self.provider})"


class ProviderBeforeAppointmentItem(models.Model):
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="before_appointment_items",
    )
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"{self.provider.name} · {self.label}"


class ProviderPhoto(models.Model):
    MEDIA_IMAGE = "image"
    MEDIA_VIDEO = "video"
    MEDIA_KIND_CHOICES = (
        (MEDIA_IMAGE, "Image"),
        (MEDIA_VIDEO, "Vidéo"),
    )

    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(upload_to="providers/gallery/", blank=True)
    image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    video = models.FileField(upload_to="providers/gallery/videos/", blank=True)
    video_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload a video or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    media_kind = models.CharField(
        max_length=16,
        choices=MEDIA_KIND_CHOICES,
        default=MEDIA_IMAGE,
    )
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Photo de {self.provider}"

    @property
    def resolved_url(self):
        if self.media_kind == self.MEDIA_VIDEO:
            if self.video:
                return self.video.url
            return self.video_url or None
        if self.image:
            return self.image.url
        return self.image_url or None

    @property
    def is_video(self):
        return self.media_kind == self.MEDIA_VIDEO

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "image"):
            compress_image_field(self.image, max_px=720, quality=80)
        return super().save(*args, **kwargs)


class ProviderZone(models.Model):
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="provider_zones"
    )
    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="zone_providers"
    )

    class Meta:
        unique_together = ("provider", "zone")

    def __str__(self):
        return f"{self.provider} - {self.zone}"


class ProviderBlockedSlot(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_EXTERNAL_BOOKED = "external_booked"
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, "Blocage manuel"),
        (SOURCE_EXTERNAL_BOOKED, "Créneau déjà pris (agenda externe)"),
    )

    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="blocked_slots"
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_recurring = models.BooleanField(
        default=False,
        help_text="Active pour bloquer un créneau récurrent (hebdomadaire).",
    )
    weekdays = models.CharField(
        max_length=20,
        blank=True,
        help_text="Jours récurrents (0=lundi … 6=dimanche), séparés par des virgules.",
    )
    starts_time = models.TimeField(null=True, blank=True)
    ends_time = models.TimeField(null=True, blank=True)
    recurrence_starts_on = models.DateField(null=True, blank=True)
    recurrence_ends_on = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    source = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, default=SOURCE_MANUAL
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("starts_at",)

    def __str__(self):
        return (
            f"{self.provider.name} indisponible du {self.starts_at} au {self.ends_at}"
        )

    def clean(self):
        super().clean()
        if self.is_recurring:
            if not self.weekdays:
                raise ValidationError(
                    "Les jours sont requis pour un blocage récurrent."
                )
            if not self.starts_time or not self.ends_time:
                raise ValidationError(
                    "L'heure de début et de fin sont requises pour un blocage récurrent."
                )
            if self.starts_time == self.ends_time:
                raise ValidationError(
                    "L'heure de fin doit être différente de l'heure de début."
                )
            if self.recurrence_starts_on and self.recurrence_ends_on:
                if self.recurrence_ends_on < self.recurrence_starts_on:
                    raise ValidationError(
                        "La fin de récurrence doit être après le début."
                    )
        else:
            if not self.starts_at or not self.ends_at:
                raise ValidationError(
                    "Le début et la fin sont requis pour un blocage ponctuel."
                )
            if self.ends_at <= self.starts_at:
                raise ValidationError(
                    "La fin du créneau bloqué doit être après le début."
                )

    @property
    def parsed_weekdays(self) -> set[int]:
        days = set()
        for raw_day in self.weekdays.split(","):
            raw_day = raw_day.strip()
            if not raw_day:
                continue
            try:
                day = int(raw_day)
            except ValueError:
                continue
            if 0 <= day <= 6:
                days.add(day)
        return days

    def matches_recurrence(self, appointment_date: date, appointment_time) -> bool:
        if not self.is_recurring or not self.starts_time or not self.ends_time:
            return False

        if self.recurrence_starts_on and appointment_date < self.recurrence_starts_on:
            return False
        if self.recurrence_ends_on and appointment_date > self.recurrence_ends_on:
            return False

        weekdays = self.parsed_weekdays
        if not weekdays or appointment_date.weekday() not in weekdays:
            return False

        if self.starts_time < self.ends_time:
            return self.starts_time <= appointment_time < self.ends_time

        # Overnight recurring block (e.g. 22:00 -> 02:00)
        return appointment_time >= self.starts_time or appointment_time < self.ends_time


class ProviderMarketingService(models.Model):
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="provider_marketing_services"
    )
    service = models.ForeignKey(
        "interface.MarketingService",
        on_delete=models.CASCADE,
        related_name="marketing_service_providers",
    )

    class Meta:
        unique_together = ("provider", "service")

    def __str__(self):
        return f"{self.provider} - {self.service}"


class Booking(models.Model):
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_PENDING_CLIENT_VALIDATION = "PENDING_CLIENT_VALIDATION"
    STATUS_AWAITING_ALTERNATIVE_PROVIDER = "AWAITING_ALTERNATIVE_PROVIDER"
    STATUS_WAITING_PROVIDER_ASSIGNMENT = "WAITING_PROVIDER_ASSIGNMENT"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_BOUNTY_OPEN = "BOUNTY_OPEN"
    STATUS_BOUNTY_CLIENT_VALIDATION = "BOUNTY_CLIENT_VALIDATION"
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, STATUS_SUBMITTED),
        (STATUS_PENDING_CLIENT_VALIDATION, STATUS_PENDING_CLIENT_VALIDATION),
        (STATUS_AWAITING_ALTERNATIVE_PROVIDER, STATUS_AWAITING_ALTERNATIVE_PROVIDER),
        (STATUS_WAITING_PROVIDER_ASSIGNMENT, STATUS_WAITING_PROVIDER_ASSIGNMENT),
        (STATUS_CONFIRMED, STATUS_CONFIRMED),
        (STATUS_CANCELLED, STATUS_CANCELLED),
        (STATUS_BOUNTY_OPEN, STATUS_BOUNTY_OPEN),
        (STATUS_BOUNTY_CLIENT_VALIDATION, STATUS_BOUNTY_CLIENT_VALIDATION),
    ]

    KIND_PROVIDER_SELECTED = "PROVIDER_SELECTED"
    KIND_GENERIC = "GENERIC"
    KIND_CHOICES = (
        (KIND_PROVIDER_SELECTED, "Provider selected"),
        (KIND_GENERIC, "Generic request"),
    )

    PAYMENT_STATUS_REQUIRES_PAYMENT = "REQUIRES_PAYMENT"
    PAYMENT_STATUS_AUTHORIZED = "AUTHORIZED"
    PAYMENT_STATUS_WAIVED = "WAIVED"
    PAYMENT_STATUS_CAPTURED = "CAPTURED"
    PAYMENT_STATUS_RELEASED = "RELEASED"
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_STATUS_REQUIRES_PAYMENT, "Requires payment"),
        (PAYMENT_STATUS_AUTHORIZED, "Authorized"),
        (PAYMENT_STATUS_WAIVED, "Waived"),
        (PAYMENT_STATUS_CAPTURED, "Captured"),
        (PAYMENT_STATUS_RELEASED, "Released"),
    )

    booking_id = models.CharField(max_length=64, unique=True)
    booking_kind = models.CharField(
        max_length=32, choices=KIND_CHOICES, default=KIND_PROVIDER_SELECTED
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    requested_marketing_service = models.ForeignKey(
        "interface.MarketingService",
        on_delete=models.SET_NULL,
        related_name="booking_intents",
        null=True,
        blank=True,
    )
    requested_marketing_sub_service = models.ForeignKey(
        "interface.MarketingSubService",
        on_delete=models.SET_NULL,
        related_name="booking_intents",
        null=True,
        blank=True,
    )
    requested_service_label_snapshot = models.CharField(max_length=255, blank=True)
    requested_options = models.JSONField(default=list, blank=True)
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=64, blank=True)
    location = models.CharField(max_length=255)
    location_preference = models.CharField(max_length=32, blank=True)
    client_address = models.TextField(blank=True)
    desired_date = models.CharField(max_length=128)
    hair_length = models.CharField(max_length=64)
    type_adjustment = models.CharField(max_length=120, blank=True)
    general_adjustments = models.JSONField(default=list, blank=True)
    meche = models.BooleanField()
    current_hair_picture = models.CharField(max_length=255, blank=True)
    inspiration_pictures = models.JSONField(default=list, blank=True)
    free_text = models.TextField(blank=True)
    estimated_price_cents = models.IntegerField()
    provider_price_estimate_cents = models.IntegerField(null=True, blank=True)
    chateau_rose_fee_cents = models.IntegerField(default=0)
    amount_due_now_cents = models.IntegerField(default=0)
    payment_status = models.CharField(
        max_length=32,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_REQUIRES_PAYMENT,
    )
    payment_auth_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=64, choices=STATUS_CHOICES)
    alternative_requested_at = models.DateTimeField(null=True, blank=True)
    proposed_price_cents = models.IntegerField(null=True, blank=True)
    locked_reservation_fee_cents = models.IntegerField(
        null=True,
        blank=True,
        help_text="Montant total effectivement payé/autorisé en acompte (modifiable pour préserver l'historique).",
    )
    proposed_date = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)
    state_entered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'entrée dans le statut courant, utilisée pour calculer son expiration.",
    )
    client_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    initial_provider_deadline_at = models.DateTimeField(null=True, blank=True)
    process_expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking_id} - {self.status}"

    @staticmethod
    def _resolve_media_url(path: str | None):
        if not path:
            return None

        parsed = urlparse(path)
        # Already absolute (http, https, etc.) or root-relative URL
        if parsed.scheme or path.startswith("/"):
            return path

        return default_storage.url(path)

    @property
    def resolved_current_hair_picture(self):
        return self._resolve_media_url(self.current_hair_picture)

    @property
    def resolved_inspiration_pictures(self):
        if not self.inspiration_pictures:
            return []

        resolved = []
        for picture in self.inspiration_pictures:
            url = self._resolve_media_url(picture)
            if url:
                resolved.append(url)
        return resolved


class BookingOpportunity(models.Model):
    REASON_GENERIC = "GENERIC"
    REASON_PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    REASON_PROVIDER_REJECTED = "PROVIDER_REJECTED"
    REASON_CHOICES = (
        (REASON_GENERIC, "Demande générique"),
        (REASON_PROVIDER_TIMEOUT, "Délai prestataire expiré"),
        (REASON_PROVIDER_REJECTED, "Refus prestataire"),
    )
    STATUS_OPEN = "OPEN"
    STATUS_OFFERED = "OFFERED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = tuple(
        (value, value)
        for value in (STATUS_OPEN, STATUS_OFFERED, STATUS_EXPIRED, STATUS_CANCELLED)
    )

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="opportunities"
    )
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)
    requested_sub_service = models.ForeignKey(
        "interface.MarketingSubService",
        on_delete=models.PROTECT,
        related_name="booking_opportunities",
    )
    excluded_provider = models.ForeignKey(
        Provider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="excluded_booking_opportunities",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    opened_at = models.DateTimeField()
    response_deadline_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("booking",),
                condition=models.Q(status="OPEN"),
                name="one_open_opportunity_per_booking",
            )
        ]

    def __str__(self):
        return f"{self.requested_sub_service} · demande {self.booking.booking_id} ({self.get_status_display()})"


class BookingOffer(models.Model):
    STATUS_PENDING_CLIENT = "PENDING_CLIENT"
    STATUS_ACCEPTED = "ACCEPTED"
    STATUS_REJECTED = "REJECTED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = tuple(
        (value, value)
        for value in (
            STATUS_PENDING_CLIENT,
            STATUS_ACCEPTED,
            STATUS_REJECTED,
            STATUS_EXPIRED,
        )
    )

    opportunity = models.OneToOneField(
        BookingOpportunity, on_delete=models.CASCADE, related_name="offer"
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name="booking_offers"
    )
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="booking_offers"
    )
    proposed_date = models.CharField(max_length=128)
    proposed_price_cents = models.PositiveIntegerField()
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING_CLIENT
    )
    submitted_at = models.DateTimeField()
    client_deadline_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Proposition de {self.provider} · demande {self.opportunity.booking.booking_id}"


class ProviderServiceFeeCoupon(models.Model):
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="service_fee_coupons",
    )
    code = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "code")

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.provider.name} · {self.code}"


class GlobalServiceFeeCoupon(models.Model):
    """Coupon that waives Château Rose fees for every booking flow."""

    code = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "code promo global"
        verbose_name_plural = "codes promo globaux"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class VerifiedReview(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "En attente de validation"),
        (STATUS_APPROVED, "Publié"),
        (STATUS_REJECTED, "Masqué / rejeté"),
    )

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="verified_review",
        null=True,
        blank=True,
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="verified_reviews"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_reviews",
    )
    client_name = models.CharField(max_length=255, blank=True)
    client_email = models.EmailField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField()
    consent_to_publish = models.BooleanField(default=False)
    is_verified = models.BooleanField(
        default=True,
        help_text="Décochez pour les avis republiés depuis une source externe autorisée.",
    )
    moderation_status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    service_performed = models.CharField(max_length=255, blank=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    provider_contested_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(is_verified=False)
                    | (
                        models.Q(booking__isnull=False)
                        & ~models.Q(client_name="")
                        & ~models.Q(client_email="")
                    )
                ),
                name="verified_review_requires_booking_and_client",
            ),
        )

    def __str__(self):
        rating = f" · {self.rating}/5" if self.rating is not None else ""
        return f"Avis vérifié {self.provider.name}{rating}"

    @property
    def is_published(self):
        return (
            self.consent_to_publish and self.moderation_status == self.STATUS_APPROVED
        )

    @property
    def public_trust_label(self):
        if self.is_verified:
            return "Réservation vérifiée"
        return "Avis client autorisé"

    @property
    def qualitative_label(self):
        if self.rating is None:
            return ""
        from chateaurose.domain.services.reviews import rating_label

        return rating_label(self.rating)

    def clean(self):
        super().clean()
        if self.is_verified and (
            not self.booking_id
            or not (self.client_name or "").strip()
            or not (self.client_email or "").strip()
        ):
            raise ValidationError(
                "Un avis vérifié doit avoir une réservation, un nom de cliente et une adresse email."
            )

    def save(self, *args, **kwargs):
        was_published = False
        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("consent_to_publish", "moderation_status")
                .first()
            )
            if previous:
                was_published = (
                    previous["consent_to_publish"]
                    and previous["moderation_status"] == self.STATUS_APPROVED
                )
        if self.rating is not None and self.rating < 1:
            self.rating = 1
        if self.rating is not None and self.rating > 5:
            self.rating = 5
        if not self.provider_id and self.booking_id:
            self.provider = self.booking.provider
        if not self.service_id and self.booking_id:
            self.service = self.booking.service
        if not self.client_name and self.booking_id:
            self.client_name = self.booking.client_name
        if not self.client_email and self.booking_id:
            self.client_email = self.booking.client_email
        if not self.service_performed and self.service_id:
            self.service_performed = self.service.name
        super().save(*args, **kwargs)
        if self.is_published and not was_published:
            self._notify_publication()

    def _notify_publication(self) -> None:
        from django.conf import settings
        from chateaurose.infrastructure.email_notifier import EmailNotifier

        recipient = getattr(
            settings, "REVIEW_PUBLISHED_NOTIFICATION_EMAIL", ""
        ) or getattr(settings, "OPERATIONS_EMAIL", "")
        if not recipient:
            return
        subject = f"Avis publié pour {self.provider.name}"
        rating_label = (
            f"{self.rating}/5" if self.rating is not None else "non renseignée"
        )
        body = (
            "Un avis vient d'être publié sur Château Rose.\n\n"
            f"Prestataire : {self.provider.name}\n"
            f"Cliente : {self.client_name}\n"
            f"Note : {rating_label}\n"
            f"Statut public : {self.public_trust_label}\n"
            f"Prestation : {self.service_performed or 'prestation Château Rose'}\n\n"
            f"Avis :\n{self.comment}"
        )
        EmailNotifier().notify(recipient, subject, body, reply_to=self.client_email)


class ReviewInvitation(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="review_invitation"
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    sent_count = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    incident_response_recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"Invitation avis {self.booking.booking_id}"
