(() => {
    const MINIMUM_NOTICE_MS = 24 * 60 * 60 * 1000;
    const NOTICE_ERROR = "Le rendez-vous doit être demandé au moins 24 heures à l'avance.";

    const sync = (input) => {
        const form = input.form;
        const error = form?.querySelector('[data-booking-datetime-error]');
        const warning = form?.querySelector('[data-nocturnal-warning]');
        const desiredAt = input.value ? new Date(input.value) : null;
        const isTooSoon = desiredAt && !Number.isNaN(desiredAt.getTime())
            && desiredAt.getTime() < Date.now() + MINIMUM_NOTICE_MS;

        input.setCustomValidity(isTooSoon ? NOTICE_ERROR : '');
        if (error) {
            error.textContent = isTooSoon ? NOTICE_ERROR : '';
            error.hidden = !isTooSoon;
        }

        const desiredTime = (input.value.split('T')[1] || '').slice(0, 5);
        if (warning) warning.hidden = isTooSoon || desiredTime <= '20:00';
        return !isTooSoon;
    };

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-booking-datetime]').forEach((input) => {
            input.addEventListener('input', () => sync(input));
            input.addEventListener('change', () => sync(input));
            sync(input);
        });
    });

    window.chateauRoseBookingDatetime = { sync };
})();
