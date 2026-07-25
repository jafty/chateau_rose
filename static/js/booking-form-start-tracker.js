(function () {
    const EVENT_NAME = 'BookingFormStarted';
    const INITIATE_CHECKOUT_SESSION_KEY = 'chateau_rose_initiate_checkout_tracked';
    const CONSENT_KEY = 'chateau_rose_marketing_consent';

    const hasMarketingConsent = () => {
        try {
            return window.localStorage && window.localStorage.getItem(CONSENT_KEY) === 'accepted';
        } catch (error) {
            return false;
        }
    };

    const safePayloadFromForm = (form) => {
        const payload = {};
        if (form.dataset.analyticsServiceSlug) payload.service_slug = form.dataset.analyticsServiceSlug;
        if (form.dataset.analyticsServiceCategory) payload.service_category = form.dataset.analyticsServiceCategory;
        if (form.dataset.analyticsStylistSelected) payload.stylist_selected = form.dataset.analyticsStylistSelected === 'true';
        if (form.dataset.analyticsBookingFlowVersion) payload.booking_flow_version = form.dataset.analyticsBookingFlowVersion;
        return payload;
    };

    const hasTrackedInitiateCheckoutThisSession = () => {
        try {
            return window.sessionStorage && window.sessionStorage.getItem(INITIATE_CHECKOUT_SESSION_KEY) === 'true';
        } catch (error) {
            return false;
        }
    };

    const markInitiateCheckoutTrackedThisSession = () => {
        try {
            if (window.sessionStorage) {
                window.sessionStorage.setItem(INITIATE_CHECKOUT_SESSION_KEY, 'true');
            }
        } catch (error) {}
    };

    class BookingFormStartTracker {
        constructor(form, adapters) {
            this.form = form;
            this.adapters = adapters || [];
            this.started = false;
            this.handleChange = this.handleChange.bind(this);
            this.form.addEventListener('change', this.handleChange, true);
            this.form.addEventListener('input', this.handleChange, true);
        }

        isEnabled() {
            return this.form.dataset.analyticsEnabled === 'true' && hasMarketingConsent();
        }

        isEligibleField(field) {
            if (!field || !field.matches || !field.matches('input, select, textarea')) return false;
            if (field.closest('[data-analytics-ignore]') || field.dataset.analyticsIgnore !== undefined) return false;
            if (field.disabled || field.readOnly) return false;
            if ((field.type || '').toLowerCase() === 'hidden') return false;
            if (['csrfmiddlewaretoken', 'payment_auth_id', 'recap_token', 'quick_checkout_id'].includes(field.name)) return false;
            return true;
        }

        handleChange(event) {
            if (this.started || !event.isTrusted || !this.isEligibleField(event.target) || !this.isEnabled()) return;
            this.markStarted();
        }

        markStarted() {
            if (this.started) return;
            this.started = true;
            const payload = safePayloadFromForm(this.form);
            this.adapters.forEach((adapter) => {
                try {
                    if (adapter && typeof adapter.trackBookingFormStarted === 'function') {
                        adapter.trackBookingFormStarted(payload);
                    }
                } catch (error) {
                    // Analytics must never affect the booking form.
                }
            });
        }

        trackInitiateCheckout() {
            if (!this.isEnabled() || hasTrackedInitiateCheckoutThisSession()) return;
            const payload = safePayloadFromForm(this.form);
            let tracked = false;
            this.adapters.forEach((adapter) => {
                try {
                    if (adapter && typeof adapter.trackInitiateCheckout === 'function') {
                        adapter.trackInitiateCheckout(payload);
                        tracked = true;
                    }
                } catch (error) {
                    // Analytics must never affect the booking form.
                }
            });
            if (tracked) {
                markInitiateCheckoutTrackedThisSession();
            }
        }
    }

    window.BookingFormStartTracker = BookingFormStartTracker;
    window.chateauRoseBookingAnalytics = window.chateauRoseBookingAnalytics || {};
    window.chateauRoseBookingAnalytics.trackInitiateCheckout = function (form) {
        if (!form) return;
        if (!form.__bookingFormStartTracker) {
            form.__bookingFormStartTracker = new BookingFormStartTracker(form, [
                window.chateauRoseMetaAnalytics,
                window.chateauRosePlausibleAnalytics,
            ]);
        }
        form.__bookingFormStartTracker.trackInitiateCheckout();
    };

    window.chateauRoseBookingAnalytics.initBookingFormStartTracking = function () {
        document.querySelectorAll('form[data-analytics-booking-form]').forEach((form) => {
            if (form.__bookingFormStartTracker) return;
            form.__bookingFormStartTracker = new BookingFormStartTracker(form, [
                window.chateauRoseMetaAnalytics,
                window.chateauRosePlausibleAnalytics,
            ]);
        });
    };

    document.addEventListener('DOMContentLoaded', window.chateauRoseBookingAnalytics.initBookingFormStartTracking);
}());
