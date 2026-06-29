(function () {
    const STORAGE_KEY = 'chateau_rose_marketing_consent';
    const banner = document.querySelector('[data-cookie-banner]');
    const acceptButton = document.querySelector('[data-cookie-accept]');
    const rejectButton = document.querySelector('[data-cookie-reject]');

    const loadMarketing = () => {
        if (typeof window.crLoadMarketingTrackers === 'function') {
            window.crLoadMarketingTrackers();
        }
    };

    const choice = window.localStorage.getItem(STORAGE_KEY);
    if (choice === 'accepted') {
        loadMarketing();
        return;
    }
    if (choice !== 'rejected' && banner) {
        banner.hidden = false;
    }

    acceptButton?.addEventListener('click', () => {
        window.localStorage.setItem(STORAGE_KEY, 'accepted');
        banner.hidden = true;
        loadMarketing();
    });

    rejectButton?.addEventListener('click', () => {
        window.localStorage.setItem(STORAGE_KEY, 'rejected');
        banner.hidden = true;
    });
}());
