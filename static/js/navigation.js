(function () {
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.main-nav');

    if (!navToggle || !navMenu) return;

    const closeMenu = () => {
        navMenu.classList.remove('is-open');
        navToggle.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
        navToggle.setAttribute('aria-label', 'Ouvrir le menu');
    };

    const openMenu = () => {
        navMenu.classList.add('is-open');
        navToggle.classList.add('is-open');
        navToggle.setAttribute('aria-expanded', 'true');
        navToggle.setAttribute('aria-label', 'Fermer le menu');
    };

    navToggle.addEventListener('click', () => {
        const isOpen = navMenu.classList.contains('is-open');
        if (isOpen) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    navMenu.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => {
            if (navMenu.classList.contains('is-open')) {
                closeMenu();
            }
        });
    });
})();
