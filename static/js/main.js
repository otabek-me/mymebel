/**
 * Mijoz qismi uchun umumiy JavaScript.
 *
 * Narx hisoblash logikasi, modal oyna va telefon niqobi shu yerda.
 */

(function () {
    'use strict';

    const menu = document.getElementById('mobile-menu');
    const menuOpen = document.getElementById('mobile-menu-open');
    const menuClose = document.getElementById('mobile-menu-close');
    if (menu && menuOpen && menuClose) {
        const menuPanel = menu.querySelector('.mobile-menu-panel');
        const backdrop = document.getElementById('mobile-menu-backdrop');
        let hideMenuTimer = null;
        const setMenuOpen = (open) => {
            window.clearTimeout(hideMenuTimer);
            if (open) {
                menu.classList.remove('hidden');
                menu.classList.add('is-visible');
                window.requestAnimationFrame(() => menu.classList.add('is-open'));
                menu.setAttribute('aria-hidden', 'false');
                menuOpen.setAttribute('aria-expanded', 'true');
                document.body.classList.add('overflow-hidden');
                menuClose.focus();
            } else {
                menu.classList.remove('is-open');
                menu.setAttribute('aria-hidden', 'true');
                menuOpen.setAttribute('aria-expanded', 'false');
                document.body.classList.remove('overflow-hidden');
                menuOpen.focus();
                hideMenuTimer = window.setTimeout(() => {
                    menu.classList.remove('is-visible');
                    menu.classList.add('hidden');
                }, 250);
            }
        };
        menuOpen.addEventListener('click', () => setMenuOpen(true));
        menuClose.addEventListener('click', () => setMenuOpen(false));
        if (backdrop) backdrop.addEventListener('click', () => setMenuOpen(false));
        menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setMenuOpen(false)));
        menu.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                event.preventDefault();
                setMenuOpen(false);
                return;
            }
            if (event.key !== 'Tab') return;
            const focusable = [...(menuPanel || menu).querySelectorAll('a[href], button:not([disabled])')];
            if (!focusable.length) return;
            if (event.shiftKey && document.activeElement === focusable[0]) {
                event.preventDefault();
                focusable[focusable.length - 1].focus();
            } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
                event.preventDefault();
                focusable[0].focus();
            }
        });
    }

    // -----------------------------------------------------------------
    // Narxni "1 250 000 so'm" ko'rinishida formatlash
    // -----------------------------------------------------------------
    window.formatPrice = function (value) {
        const num = Math.round(Number(value) || 0);
        return num.toLocaleString('ru-RU').replace(/ /g, ' ') + " so'm";
    };

    // -----------------------------------------------------------------
    // Telefon raqami niqobi: +998 XX XXX XX XX
    // -----------------------------------------------------------------
    window.attachPhoneMask = function (input) {
        if (!input) return;
        input.addEventListener('input', function () {
            let digits = input.value.replace(/\D/g, '');
            // +998 ni boshidan olib tashlaymiz (agar kiritilgan bo'lsa)
            if (digits.startsWith('998')) digits = digits.slice(3);
            digits = digits.slice(0, 9);

            let out = '+998';
            if (digits.length > 0) out += ' ' + digits.slice(0, 2);
            if (digits.length > 2) out += ' ' + digits.slice(2, 5);
            if (digits.length > 5) out += ' ' + digits.slice(5, 7);
            if (digits.length > 7) out += ' ' + digits.slice(7, 9);
            input.value = out;
        });
        input.addEventListener('focus', function () {
            if (!input.value) input.value = '+998 ';
        });
    };

    // -----------------------------------------------------------------
    // Lightbox (rasmni kattalashtirish)
    // -----------------------------------------------------------------
    window.openLightbox = function (src) {
        const lb = document.getElementById('lightbox');
        if (!lb) return;
        lb.querySelector('img').src = src;
        lb.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    };

    window.closeLightbox = function () {
        const lb = document.getElementById('lightbox');
        if (!lb) return;
        lb.classList.add('hidden');
        document.body.style.overflow = '';
    };

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            window.closeLightbox();
            const modal = document.getElementById('inquiry-modal');
            if (modal && !modal.classList.contains('hidden')) {
                window.closeInquiryModal && window.closeInquiryModal();
            }
        }
    });
})();
