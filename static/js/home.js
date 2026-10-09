(function () {
    'use strict';

    const header = document.getElementById('site-header');
    const homeHero = document.getElementById('home-hero');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    if (header && header.classList.contains('site-header--home')) {
        const updateHeader = () => header.classList.toggle('is-scrolled', window.scrollY > 40);
        updateHeader();
        window.addEventListener('scroll', updateHeader, { passive: true });
    }

    const carousel = document.querySelector('[data-carousel]');
    if (carousel) {
        const slides = [...carousel.querySelectorAll('[data-slide]')];
        const indicators = [...document.querySelectorAll('[data-indicator]')];
        const controls = document.querySelector('.hero-controls');
        const pauseRegion = homeHero || carousel;
        if (!slides.length) return;

        let index = Math.max(0, slides.findIndex((slide) => slide.classList.contains('is-active')));
        let timer = null;
        let deadline = null;
        let remaining = 6000;
        const pauseReasons = new Set();
        const completedSlides = new Set();
        const queuedTransitions = [];
        const imageLoads = new Map();
        const counter = document.querySelector('[data-carousel-count]');
        let transitioning = false;
        let transitionTarget = null;
        const transitionDuration = reducedMotion.matches ? 300 : 1100;

        const syncPauseState = () => {
            const paused = pauseReasons.size > 0 || document.hidden;
            carousel.classList.toggle('is-paused', paused);
            if (controls) controls.classList.toggle('is-paused', paused);
        };

        const stopTimer = () => {
            if (timer !== null) window.clearTimeout(timer);
            timer = null;
            if (deadline !== null) remaining = Math.max(0, deadline - Date.now());
            deadline = null;
        };
        const schedule = (reset = false) => {
            if (reset) remaining = 6000;
            if (timer !== null) window.clearTimeout(timer);
            timer = null;
            deadline = null;
            if (slides.length < 2 || pauseReasons.size || document.hidden) return;
            deadline = Date.now() + remaining;
            timer = window.setTimeout(() => {
                timer = null;
                deadline = null;
                remaining = 6000;
                navigateBy(1);
            }, remaining);
        };
        const setPauseReason = (reason, paused) => {
            if (paused) {
                if (pauseReasons.has(reason)) return;
                pauseReasons.add(reason);
                stopTimer();
            } else {
                if (!pauseReasons.has(reason)) return;
                pauseReasons.delete(reason);
                schedule();
            }
            syncPauseState();
        };

        const normalizeIndex = (value) => (value + slides.length) % slides.length;
        const prepareImage = (slideIndex) => {
            const image = slides[slideIndex].querySelector('img');
            if (!image) return Promise.reject(new Error('Slayd rasmi topilmadi.'));
            image.loading = 'eager';
            image.fetchPriority = 'low';
            if (image.complete) {
                return image.naturalWidth
                    ? Promise.resolve()
                    : Promise.reject(new Error(`Slayd rasmi yuklanmadi: ${image.currentSrc || image.src}`));
            }
            if (imageLoads.has(slideIndex)) return imageLoads.get(slideIndex);
            const load = new Promise((resolve, reject) => {
                const cleanUp = () => {
                    image.removeEventListener('load', loaded);
                    image.removeEventListener('error', failed);
                };
                const loaded = () => {
                    cleanUp();
                    image.naturalWidth ? resolve() : reject(new Error('Slayd rasmini ochib bo‘lmadi.'));
                };
                const failed = () => {
                    cleanUp();
                    reject(new Error(`Slayd rasmi yuklanmadi: ${image.currentSrc || image.src}`));
                };
                image.addEventListener('load', loaded, { once: true });
                image.addEventListener('error', failed, { once: true });
                if (image.complete) loaded();
            });
            imageLoads.set(slideIndex, load);
            return load.finally(() => imageLoads.delete(slideIndex));
        };
        const refreshIndicators = () => {
            indicators.forEach((indicator, indicatorIndex) => {
                indicator.classList.toggle('is-complete', completedSlides.has(indicatorIndex));
                indicator.classList.remove('is-active');
                indicator.removeAttribute('aria-current');
            });
            if (indicators[index]) {
                void indicators[index].offsetWidth;
                indicators[index].classList.add('is-active');
                indicators[index].setAttribute('aria-current', 'true');
            }
            if (counter) counter.textContent = `${String(index + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
        };
        const requestShow = async (nextIndex, direction) => {
            const normalized = normalizeIndex(nextIndex);
            if (transitioning) {
                stopTimer();
                remaining = 6000;
                if (normalized !== transitionTarget) queuedTransitions.push({ target: normalized, direction });
                return;
            }
            if (normalized === index) {
                refreshIndicators();
                schedule(true);
                return;
            }

            stopTimer();
            remaining = 6000;
            transitioning = true;
            transitionTarget = normalized;
            try {
                await prepareImage(normalized);
            } catch (error) {
                transitioning = false;
                transitionTarget = null;
                console.error('Keyingi banner rasmi tayyor emas:', error);
                schedule(true);
                return;
            }

            const previousSlide = slides[index];
            const wrapped = index === slides.length - 1 && normalized === 0;
            if (wrapped) completedSlides.clear();
            else completedSlides.add(index);
            completedSlides.delete(normalized);
            slides.forEach((slide) => slide.classList.remove('is-prev'));
            previousSlide.classList.remove('is-active');
            previousSlide.classList.remove('is-ken-burns');
            previousSlide.classList.add('is-prev');
            previousSlide.setAttribute('aria-hidden', 'true');
            previousSlide.setAttribute('inert', '');
            index = normalized;
            const activeSlide = slides[index];
            activeSlide.dataset.direction = direction;
            activeSlide.classList.remove('is-ken-burns');
            activeSlide.classList.add('is-active');
            activeSlide.removeAttribute('aria-hidden');
            activeSlide.removeAttribute('inert');
            refreshIndicators();
            syncPauseState();
            schedule(true);
            prepareImage((index + 1) % slides.length).catch((error) => {
                console.error('Keyingi banner rasmi oldindan yuklanmadi:', error);
            });
            window.setTimeout(() => {
                if (!reducedMotion.matches && activeSlide.classList.contains('is-active')) {
                    activeSlide.classList.add('is-ken-burns');
                }
                previousSlide.classList.remove('is-prev');
                transitioning = false;
                transitionTarget = null;
                if (queuedTransitions.length) {
                    const next = queuedTransitions.shift();
                    requestShow(next.target, next.direction);
                }
            }, transitionDuration);
        };
        const navigateBy = (delta) => {
            const base = queuedTransitions.length
                ? queuedTransitions[queuedTransitions.length - 1].target
                : (transitionTarget === null ? index : transitionTarget);
            requestShow(base + delta, delta < 0 ? 'prev' : 'next');
        };
        const navigateTo = (target) => {
            const base = queuedTransitions.length
                ? queuedTransitions[queuedTransitions.length - 1].target
                : (transitionTarget === null ? index : transitionTarget);
            const normalized = normalizeIndex(target);
            requestShow(normalized, normalized < base ? 'prev' : 'next');
        };

        if (slides.length < 2) {
            carousel.classList.add('is-single');
            if (controls) controls.hidden = true;
        }
        document.querySelector('[data-carousel-prev]')?.addEventListener('click', () => navigateBy(-1));
        document.querySelector('[data-carousel-next]')?.addEventListener('click', () => navigateBy(1));
        indicators.forEach((button) => button.addEventListener('click', () => navigateTo(Number(button.dataset.indicator))));

        pauseRegion.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowLeft') {
                event.preventDefault();
                navigateBy(-1);
            } else if (event.key === 'ArrowRight') {
                event.preventDefault();
                navigateBy(1);
            }
        });
        pauseRegion.addEventListener('mouseenter', () => setPauseReason('hover', true));
        pauseRegion.addEventListener('mouseleave', () => setPauseReason('hover', false));
        pauseRegion.addEventListener('focusin', () => setPauseReason('focus', true));
        pauseRegion.addEventListener('focusout', (event) => {
            if (!pauseRegion.contains(event.relatedTarget)) setPauseReason('focus', false);
        });
        let pointerStart = null;
        let dragged = false;
        let suppressClick = false;
        pauseRegion.addEventListener('pointerdown', (event) => {
            setPauseReason('pointer', true);
            if (!carousel.contains(event.target) || (event.pointerType === 'mouse' && event.button !== 0)) return;
            if (event.target.closest('a, button')) return;
            pointerStart = { id: event.pointerId, x: event.clientX, y: event.clientY, type: event.pointerType };
            dragged = false;
        });
        window.addEventListener('pointermove', (event) => {
            if (!pointerStart || pointerStart.id !== event.pointerId || dragged) return;
            const deltaX = event.clientX - pointerStart.x;
            const deltaY = event.clientY - pointerStart.y;
            const threshold = pointerStart.type === 'mouse' ? 60 : 50;
            if (Math.abs(deltaX) >= threshold && Math.abs(deltaX) > Math.abs(deltaY)) {
                dragged = true;
                suppressClick = true;
                navigateBy(deltaX < 0 ? 1 : -1);
            }
        }, { passive: true });
        const finishPointer = (event) => {
            if (pointerStart && pointerStart.id === event.pointerId) {
                pointerStart = null;
                window.setTimeout(() => {
                    dragged = false;
                    suppressClick = false;
                }, 0);
            }
            setPauseReason('pointer', false);
        };
        window.addEventListener('pointerup', finishPointer);
        window.addEventListener('pointercancel', finishPointer);
        carousel.addEventListener('click', (event) => {
            if (!suppressClick) return;
            event.preventDefault();
            event.stopPropagation();
            suppressClick = false;
        }, true);
        document.addEventListener('visibilitychange', () => {
            setPauseReason('hidden', document.hidden);
        });

        refreshIndicators();
        if (document.hidden) pauseReasons.add('hidden');
        syncPauseState();
        if (slides.length > 1) {
            prepareImage((index + 1) % slides.length).catch((error) => {
                console.error('Keyingi banner rasmi oldindan yuklanmadi:', error);
            });
        }
        window.setTimeout(() => {
            if (!reducedMotion.matches) slides[index].classList.add('is-ken-burns');
        }, transitionDuration);
        schedule();
    }

    if ('IntersectionObserver' in window && !reducedMotion.matches) {
        const observer = new IntersectionObserver((entries, currentObserver) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-revealed');
                currentObserver.unobserve(entry.target);
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
        document.querySelectorAll('[data-reveal]').forEach((element) => observer.observe(element));
    } else {
        document.querySelectorAll('[data-reveal]').forEach((element) => element.classList.add('is-revealed'));
    }

    if (homeHero) {
        homeHero.addEventListener('dragstart', (event) => {
            if (event.target.closest('img')) event.preventDefault();
        });
    }
})();
