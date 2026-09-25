// Fast Check In / Check Out switching for the existing Flask routes.
// The other screen is preloaded once, then the already loaded page is shown immediately.
// Forms still submit to Flask, so no database or app.py changes are needed.
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
    function showScreen(mode, nodes) {
        if (!main || !active) return;
        saved[active] = Array.from(main.childNodes);
        main.replaceChildren(...nodes);
        active = mode;
        const switcher = main.querySelector('.visit-switch');
        if (switcher) {
            switcher.dataset.currentMode = mode;
            switcher.querySelectorAll('a[data-mode]').forEach(link => {
                if (link.dataset.mode === mode) link.setAttribute('aria-current', 'page');
                else link.removeAttribute('aria-current');
            });
        }
        main.classList.remove('switch-enter');
        void main.offsetWidth;
        main.classList.add('switch-enter');
        document.title = mode === 'in' ? 'Visitor Check In' : 'Visitor Check Out';
        window.scrollTo({ top: 0, behavior: 'instant' });
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
        if (event.target.id === 'liveSearch') {
            const term = event.target.value.trim().toLocaleLowerCase();
            const cards = [...document.querySelectorAll('.visitor-result-card')];
            let visible = 0;
            cards.forEach(card => {
                const match = (card.dataset.search || '').includes(term);
                card.classList.toggle('hidden', !match);
                if (match) visible++;
            });
            const count = document.getElementById('visitorCount');
            const noMatch = document.getElementById('checkoutNoMatch');
            if (count) count.textContent = visible;
            if (noMatch) noMatch.classList.toggle('hidden', !cards.length || visible > 0);
        }
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
});
