// Fast Check In / Check Out switching for the existing Flask routes.
// The other screen is preloaded once, then the already loaded page is shown immediately.
// Forms still submit to Flask, so no database or app.py changes are needed.

const companies = [
    'Amazon',
    'Apple',
    'Applied Materials',
    'Blueward',
    'Bosch',
    'Caterpillar',
    'Cisco',
    'DHL',
    'Emergous',
    'FedEx',
    'FNS, Inc',
    'Ford',
    'Foxconn',
    'GE Aerospace',
    'GE Vernova',
    'General Motors',
    'Google',
    'Greenery Resources',
    'Honeywell',
    'Hyundai',
    'IBM',
    'Intel',
    'INTOR',
    'KLA',
    'Korea Container Pool',
    'LG Chem',
    'LG Electronics',
    'LG Energy Solution',
    'Lockheed Martin',
    'LS Electric',
    'LG CNS',
    'Lucid Motors',
    'Maersk',
    'Meta',
    'Microsoft',
    'Mitsubishi Electric',
    'NextStar Energy',
    'NVIDIA',
    'Panasonic',
    'Phoenix Contact',
    'Prokhon',
    'Qualcomm',
    'Rivian',
    'RTX',
    'Samsung Electronics',
    'Samsung SDS',
    'Schneider Electric',
    'Siemens',
    'SK hynix',
    'Sony',
    'SPEO',
    'Tesla',
    'Texas Instruments',
    'Tongfei',
    'TSMC',
    'UPS',
    'Verizon',
    'Walmart',
    'Logitech',
    'Lucid Motors',
    'Lenovo',
];

window.__visitAudioCtx = null;
window.__visitChimeAt = 0;
window.playSuccessChime = function playSuccessChime() {
    try {
        var now = Date.now();
        if (now - window.__visitChimeAt < 2000) return;
        window.__visitChimeAt = now;
        try { sessionStorage.setItem('visitChimeAt', String(now)); } catch (e) { }
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        if (!window.__visitAudioCtx || window.__visitAudioCtx.state === 'closed') {
            window.__visitAudioCtx = new Ctx();
        }
        var ctx = window.__visitAudioCtx;
        function tone(freq, start, dur, vol) {
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.0001, start);
            gain.gain.exponentialRampToValueAtTime(vol, start + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(start);
            osc.stop(start + dur + 0.02);
        }
        function go() {
            var t0 = ctx.currentTime;
            // DING
            tone(880, t0, 0.7, 1.35);
            tone(1760, t0, 0.5, 0.50);

            // DONG
            tone(659.25, t0 + 0.5, 1.0, 1.40);
            tone(1318.5, t0 + 0.5, 0.75, 0.45);

            //Ding 첫번째 소리
            //tone(659.25, t0, 0.2, 1.0);
            //tone(880.0, t0 + 0.08, 0.28, 0.9);
        }
        if (ctx.state === 'suspended') ctx.resume().then(go).catch(function () { });
        else go();
    } catch (e) { }
};

document.addEventListener('pointerdown', function unlockVisitAudioOnce() {
    try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        if (!window.__visitAudioCtx || window.__visitAudioCtx.state === 'closed') {
            window.__visitAudioCtx = new Ctx();
        }
        if (window.__visitAudioCtx.state === 'suspended') {
            window.__visitAudioCtx.resume().catch(function () { });
        }
    } catch (e) { }
}, { once: true, capture: true, passive: true });

document.addEventListener('DOMContentLoaded', () => {
    const main = document.getElementById('app-main');
    const firstSwitch = main?.querySelector('.visit-switch');
    const paths = firstSwitch ? {
        in: firstSwitch.querySelector('[data-mode="in"]')?.getAttribute('href'),
        out: firstSwitch.querySelector('[data-mode="out"]')?.getAttribute('href'),
    } : null;
    let active = firstSwitch?.dataset.currentMode || null;
    const saved = {};
    const loading = {};
    let navigationToken = 0;

    document.addEventListener('submit', function (event) {
        if (event.defaultPrevented) return;
        var form = event.target;
        if (!(form instanceof HTMLFormElement) || form.dataset.soundSubmitted === '1') return;
        var isCheckIn = !!form.querySelector('[name="visitor_name"]');
        var action = (form.getAttribute('action') || '').toLowerCase();
        var isCheckoutConfirm = action.indexOf('checkout/confirm') !== -1 || !!form.querySelector('[name="checkout_comment"]');
        if (!isCheckIn && !isCheckoutConfirm) return;
        event.preventDefault();
        form.dataset.soundSubmitted = '1';
        window.playSuccessChime();
        form.querySelectorAll('button[type="submit"]').forEach(function (btn) { btn.disabled = true; });
        setTimeout(function () {
            HTMLFormElement.prototype.submit.call(form);
        }, 900);
    });

    // Smooth wheel scrolling on desktop. Keep native touch scrolling and reduced-motion behavior.
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let smoothScroll = null;
    if (!prefersReducedMotion.matches && typeof window.Lenis === 'function') {
        try {
            smoothScroll = new window.Lenis({
                duration: 1.05,
                smoothWheel: true,
                smoothTouch: false,
                wheelMultiplier: 0.85,
                touchMultiplier: 1
            });
            const scrollFrame = time => {
                smoothScroll.raf(time);
                requestAnimationFrame(scrollFrame);
            };
            requestAnimationFrame(scrollFrame);
        } catch (error) {
            // CDN/runtime issues should never block visitor check-in or check-out.
            smoothScroll = null;
        }
    }

    // Reveal only specifically marked elements; no JS or reduced motion = instantly visible.
    const revealObserver = !prefersReducedMotion.matches && 'IntersectionObserver' in window
        ? new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.06, rootMargin: '0px 0px -24px 0px' })
        : null;

    function initializeReveals(container) {
        container.querySelectorAll('[data-scroll-reveal]').forEach(el => {
            if (el.classList.contains('is-visible')) return;
            if (!revealObserver) {
                el.classList.remove('scroll-reveal-ready');
                el.classList.add('is-visible');
                return;
            }
            // Mark before observing so the reveal animates only when in view.
            el.classList.add('scroll-reveal-ready');
            revealObserver.observe(el);
        });
    }
    if (main) initializeReveals(main);

    // Parse ONLY the body of our own two registration routes, never execute fetched scripts.
    async function loadScreen(mode, force = false) {
        if (!paths?.[mode]) throw new Error('Route missing');
        if (!force && saved[mode]) return saved[mode];
        if (!force && loading[mode]) return loading[mode];
        const promise = fetch(paths[mode], { credentials: 'same-origin', headers: { 'X-Requested-With': 'Fetch' } })
            .then(response => {
                if (!response.ok) throw new Error('Page could not be loaded');
                return response.text();
            })
            .then(html => {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const content = doc.querySelector('#app-main');
                const switcher = content?.querySelector('.visit-switch');
                if (!content || switcher?.dataset.currentMode !== mode) throw new Error('Unexpected page');
                const nodes = Array.from(content.childNodes);
                if (!force || !saved[mode]) saved[mode] = nodes;
                return nodes;
            });
        if (!force) loading[mode] = promise;
        try { return await promise; }
        finally { if (!force) delete loading[mode]; }
    }

    // Put current DOM nodes aside rather than recreating them: typed form values survive switching.
    function isHeaderNode(node) {
        return node && node.nodeType === 1 && (
            node.classList.contains('visit-page-header') ||
            (node.classList.contains('mb-7') && node.querySelector('.visit-switch'))
        );
    }

    function showScreen(mode, nodes) {
        if (!main || !active) return;
        const previousMode = active;
        const nodeList = Array.from(nodes);

        // Clone header when saving so title text is kept per mode (not shared with live toggle).
        saved[active] = Array.from(main.childNodes).map(n =>
            isHeaderNode(n) ? n.cloneNode(true) : n
        );

        const liveHeader = Array.from(main.childNodes).find(isHeaderNode);
        const incomingHeader = nodeList.find(isHeaderNode);
        const incomingBody = nodeList.filter(n => !isHeaderNode(n));

        if (liveHeader && incomingHeader) {
            const liveCopy = liveHeader.querySelector('.visit-page-copy') || liveHeader.firstElementChild;
            const nextCopy = incomingHeader.querySelector('.visit-page-copy') || incomingHeader.firstElementChild;
            if (liveCopy && nextCopy) liveCopy.innerHTML = nextCopy.innerHTML;

            const switcher = liveHeader.querySelector('.visit-switch');
            if (switcher) {
                switcher.querySelectorAll('a[data-mode]').forEach(link => {
                    if (link.dataset.mode === mode) link.setAttribute('aria-current', 'page');
                    else link.removeAttribute('aria-current');
                });
                if (switcher.dataset.currentMode !== mode) {
                    switcher.dataset.currentMode = previousMode;
                    void switcher.offsetWidth;
                    requestAnimationFrame(() => {
                        switcher.dataset.currentMode = mode;
                    });
                } else {
                    switcher.dataset.currentMode = mode;
                }
            }

            Array.from(main.childNodes).forEach(child => {
                if (child !== liveHeader) child.remove();
            });
            incomingBody.forEach(n => main.appendChild(n));
        } else {
            main.replaceChildren(...nodeList);
            const switcher = main.querySelector('.visit-switch');
            if (switcher) {
                switcher.dataset.currentMode = mode;
                switcher.querySelectorAll('a[data-mode]').forEach(link => {
                    if (link.dataset.mode === mode) link.setAttribute('aria-current', 'page');
                    else link.removeAttribute('aria-current');
                });
            }
        }

        active = mode;
        main.classList.remove('switch-enter');
        document.title = mode === 'in' ? 'Visitor Check In' : 'Visitor Check Out';
        if (smoothScroll) smoothScroll.scrollTo(0, { immediate: true });
        else window.scrollTo(0, 0);
        initializeReveals(main);
    }

    async function navigate(mode, pushHistory = true) {
        if (!paths || !active || !main || mode === active || !paths[mode]) return;
        const token = ++navigationToken;
        const source = main.querySelector('.visit-switch');
        // Move the slider immediately even if the destination is still loading.
        if (source) source.dataset.currentMode = mode;
        const destinationUrl = paths[mode];
        try {
            const nodes = await loadScreen(mode);
            if (token !== navigationToken) return;
            showScreen(mode, nodes);
            if (pushHistory) history.pushState({ visitMode: mode }, '', destinationUrl);
            // Warm the other view, so switching back does not request a new page.
            const other = mode === 'in' ? 'out' : 'in';
            if (!saved[other]) loadScreen(other).catch(() => { });
        } catch (error) {
            // Normal navigation remains a safe fallback if preloading fails.
            window.location.assign(destinationUrl);
        }
    }

    if (active && paths?.in && paths?.out) {
        // Fetch the other view in the background; no 420ms artificial delay.
        loadScreen(active === 'in' ? 'out' : 'in').catch(() => { });
        history.replaceState({ visitMode: active }, '', window.location.href);
        document.addEventListener('click', event => {
            const link = event.target.closest('a[href]');
            if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const target = Object.entries(paths).find(([, path]) => new URL(path, location.href).pathname === link.pathname);
            if (!target || (link.target && link.target !== '_self') || link.hasAttribute('download')) return;
            event.preventDefault();
            navigate(target[0]);
        });
        window.addEventListener('popstate', () => {
            const target = Object.entries(paths).find(([, path]) => new URL(path, location.href).pathname === location.pathname);
            if (target) navigate(target[0], false);
            else location.reload();
        });
    }

    // Event delegation: input events still work for dynamically displayed Check Out cards.
    document.addEventListener('input', event => {

        // Visitor Phone auto-format
        if (event.target.id === 'visitor_phone') {
            let value = event.target.value.replace(/\D/g, '').slice(0, 10);

            if (value.length > 6) {
                value = value.replace(/(\d{3})(\d{3})(\d+)/, '$1-$2-$3');
            } else if (value.length > 3) {
                value = value.replace(/(\d{3})(\d+)/, '$1-$2');
            }

            event.target.value = value;
        }

        // Company autocomplete
        if (event.target.id === 'company') {
            const input = event.target;
            const term = input.value.trim().toLowerCase();
            const suggestions = document.getElementById('companySuggestions');

            if (!suggestions) return;

            const matches = companies.filter(company =>
                company.toLowerCase().includes(term)
            );

            suggestions.innerHTML = '';

            if (!term || matches.length === 0) {
                suggestions.classList.add('hidden');
                return;
            }

            matches.forEach(company => {
                const option = document.createElement('button');

                option.type = 'button';
                option.textContent = company;
                option.className =
                    'company-option block w-full px-4 py-3 text-left text-sm text-slate-700 transition-colors hover:bg-[#F4F7FA] hover:text-[#003A70] focus:bg-[#F4F7FA] focus:text-[#003A70] focus:outline-none focus:ring-0';
                option.addEventListener('click', () => {
                    input.value = company;
                    suggestions.classList.add('hidden');

                });

                suggestions.appendChild(option);
            });

            suggestions.classList.remove('hidden');
        }

        // Check Out live search
        if (event.target.id === 'liveSearch') {
            const term = event.target.value.trim().toLocaleLowerCase();
            const cards = [...document.querySelectorAll('.visitor-result-card')];
            let visible = 0;

            cards.forEach(card => {
                const hay = (card.dataset.search || '').toLocaleLowerCase();
                const match = !term || hay.includes(term);

                card.classList.toggle('is-search-hidden', !match);
                card.classList.toggle('hidden', !match);

                if (match) visible++;
            });

            const count = document.getElementById('visitorCount');
            const noMatch = document.getElementById('checkoutNoMatch');

            if (count) count.textContent = visible;
            if (noMatch) noMatch.classList.toggle('hidden', !cards.length || visible > 0);
        }

        // Admin live search
        if (event.target.id === 'adminLiveSearch') {
            const term = event.target.value.trim().toLocaleLowerCase();
            const rows = [...document.querySelectorAll('.admin-record')];
            let visible = 0;

            rows.forEach(row => {
                const match = (row.dataset.search || '').includes(term);
                row.classList.toggle('hidden', !match);

                if (match) visible++;
            });

            const count = document.getElementById('adminVisibleCount');

            if (count) count.textContent = visible;
        }
    });

    document.addEventListener('keydown', event => {
        const suggestions = document.getElementById('companySuggestions');

        // Company 입력창에서 ↓ 누르면 첫 번째 드롭다운 항목으로 이동
        if (event.target.id === 'company' && event.key === 'ArrowDown') {
            if (!suggestions || suggestions.classList.contains('hidden')) return;

            const options = suggestions.querySelectorAll('.company-option');

            if (options.length > 0) {
                event.preventDefault();
                options[0].focus();
            }

            return;
        }

        // 드롭다운 항목 안에서 키보드 이동
        if (event.target.classList.contains('company-option')) {
            const options = [...suggestions.querySelectorAll('.company-option')];
            const currentIndex = options.indexOf(event.target);

            if (event.key === 'ArrowDown') {
                event.preventDefault();

                const nextIndex =
                    currentIndex < options.length - 1
                        ? currentIndex + 1
                        : 0;

                options[nextIndex].focus();
            }

            else if (event.key === 'ArrowUp') {
                event.preventDefault();

                // 첫 번째 항목에서 ↑ 누르면 Company 입력창으로 돌아감
                if (currentIndex === 0) {
                    document.getElementById('company')?.focus();
                } else {
                    options[currentIndex - 1].focus();
                }
            }

            else if (event.key === 'Enter') {
                event.preventDefault();
                event.target.click();
            }

            else if (event.key === 'Escape') {
                event.preventDefault();
                suggestions.classList.add('hidden');
                document.getElementById('company')?.focus();
            }
        }
    });
});
