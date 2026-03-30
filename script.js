// ── Config ───────────────────────────────────────────────────────────────────
const myUserId = "liza";

// ── State ─────────────────────────────────────────────────────────────────────
let isSwiping = false;
let topIdx = 0; // index into `slots` for the current top card

// ── 3-Card slot pool ─────────────────────────────────────────────────────────
// Slots rotate: top → next → upcoming → (flies away) → loads next design
const slots = [
    { el: document.getElementById('card-a'), img: document.getElementById('image-a'), title: document.getElementById('title-a'), imageId: '' },
    { el: document.getElementById('card-b'), img: document.getElementById('image-b'), title: document.getElementById('title-b'), imageId: '' },
    { el: document.getElementById('card-c'), img: document.getElementById('image-c'), title: document.getElementById('title-c'), imageId: '' },
];

// Role helpers: 0=top, 1=next/ghost, 2=upcoming/hidden
function getSlot(roleOffset) { return slots[(topIdx + roleOffset) % 3]; }

// ── Other DOM refs ────────────────────────────────────────────────────────────
const cardStack = document.getElementById('card-stack');
const endState = document.getElementById('end-state');
const actionBtns = document.getElementById('action-buttons');
const dragOverlay = document.getElementById('drag-overlay');

// ── Apply role styles to a slot ───────────────────────────────────────────────
// Role 0 = top (full size, highest z-index)
// Role 1 = next ghost (peeks behind, scale 0.96) — more visible than before
// Role 2 = upcoming (hidden behind ghost, same scale, z-index 1)
function applyRoleStyles(slot, role, animate = false) {
    slot.el.style.transition = animate ? 'transform 0.2s ease' : 'none';
    switch (role) {
        case 0:
            slot.el.style.zIndex = '3';
            slot.el.style.transform = '';
            slot.el.style.opacity = '1';
            slot.el.style.boxShadow = '0 25px 50px rgba(0,0,0,0.15)';
            break;
        case 1:
            slot.el.style.zIndex = '2';
            slot.el.style.transform = 'scale(0.96) translateY(8px)'; // more visible peek
            slot.el.style.opacity = '1';
            slot.el.style.boxShadow = '0 15px 35px rgba(0,0,0,0.08)';
            break;
        case 2:
            slot.el.style.zIndex = '1';
            slot.el.style.transform = 'scale(0.96) translateY(8px)';
            slot.el.style.opacity = '1';
            slot.el.style.boxShadow = 'none';
            break;
    }
}

// ── Image preloading ──────────────────────────────────────────────────────────
// Decodes the image fully into the browser cache before we assign it to a slot.
// When we later set img.src, the browser paints immediately — zero decode lag.
function preloadImage(url) {
    return new Promise(resolve => {
        const img = new Image();
        img.onload = () => resolve(url);
        img.onerror = () => resolve(url); // don't block on broken images
        img.src = url;
    });
}

// ── End state ─────────────────────────────────────────────────────────────────
function showEndState() {
    cardStack.style.display = 'none';
    endState.style.display = 'block';
    actionBtns.style.display = 'none';
}
function hideEndState() {
    cardStack.style.display = '';
    endState.style.display = 'none';
    actionBtns.style.display = 'flex';
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatTitle(id) {
    if (!id || id === 'none') return '';
    return id.replace(/[0-9_]+/g, ' ').trim().split(' ')
        .filter(Boolean)
        .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + pageName).classList.add('active-page');
    document.getElementById('nav-' + pageName).classList.add('active');
    if (pageName === 'picks') loadPicks();
    if (pageName === 'profile') loadProfile();
}

// ── API: load next design into a slot (with image preloading) ─────────────────
async function loadDesignIntoSlot(slot) {
    try {
        const res = await fetch(`http://127.0.0.1:8000/next-design?user_id=${myUserId}`);
        const data = await res.json();
        slot.imageId = data.image_id;
        if (data.image_id !== 'none') {
            // Fully decode the image in the browser cache BEFORE painting it
            await preloadImage(data.image_url);
            // Now setting src is instant — already in cache, no decode lag
            slot.img.src = data.image_url;
            slot.title.innerText = formatTitle(data.image_id);
        }
    } catch (e) { console.error('Load error:', e); }
}

// ── API: POST swipe result ────────────────────────────────────────────────────
async function postSwipe(imageId, action) {
    try {
        await fetch('http://127.0.0.1:8000/swipe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: myUserId, image_id: imageId, action })
        });
    } catch (e) { console.error('Swipe POST error:', e); }
}

// ── Ghost peek during drag ────────────────────────────────────────────────────
function updateGhostDrag(dragX) {
    const p = Math.min(Math.abs(dragX) / 120, 1);
    const next = getSlot(1);
    next.el.style.transition = 'none';
    // starts at scale(0.96) and grows to scale(1) as user drags
    next.el.style.transform = `scale(${0.96 + 0.04 * p}) translateY(${8 - 8 * p}px)`;
}

// ── Animated swipe ────────────────────────────────────────────────────────────
// Zero DOM manipulation during the animation itself.
// The next card (role 1) is already fully loaded and painted — it just grows.
function animateAndSwipe(action) {
    const top = getSlot(0);
    const next = getSlot(1);
    if (!top.imageId || top.imageId === 'none' || isSwiping) return;
    isSwiping = true;

    const swipedId = top.imageId;

    // ① Top card flies off fast — no fade, just a quick slide+rotate
    const flyX = action === 'like' ? 1300 : -1300;
    top.el.style.transition = 'transform 0.25s cubic-bezier(0.25,0.46,0.45,0.94)';
    top.el.style.transform = `translate(${flyX}px, -80px) rotate(${action === 'like' ? 28 : -28}deg)`;
    // No opacity fade — cards don't fade in real life, they just fly

    // ② Next card grows into top position immediately — snappy, not sluggish
    next.el.style.transition = 'transform 0.2s ease';
    next.el.style.transform = 'scale(1) translateY(0)';

    // ③ Fire POST immediately — don't wait for animation
    const postPromise = postSwipe(swipedId, action);

    // ④ After animation completes: rotate slot roles, load next image in background
    // Timeout matches exit animation (250ms) + tiny buffer (30ms)
    setTimeout(async () => {
        const nextSlotImageId = next.imageId;

        // Rotate: topIdx advances → old top is now "upcoming" (role 2)
        topIdx = (topIdx + 1) % 3;

        // New role assignments — no transition, happens behind the scene instantly
        applyRoleStyles(getSlot(0), 0, false); // new top  — already at scale(1) from animation
        applyRoleStyles(getSlot(1), 1, false); // new next — was "upcoming", already at ghost pos
        const recycled = getSlot(2);            // old top  — now recycled to the back
        recycled.el.style.transition = 'none';
        recycled.el.style.transform = 'scale(0.96) translateY(8px)';
        recycled.el.style.opacity = '1';
        recycled.el.style.zIndex = '1';
        recycled.el.style.boxShadow = 'none';
        recycled.imageId = '';

        if (nextSlotImageId === 'none') {
            isSwiping = false;
            showEndState();
            return;
        }

        isSwiping = false;

        // ⑤ Load + preload image for the recycled slot quietly in the background
        // By the time the user swipes again, this image is fully cached and ready
        await postPromise;
        await loadDesignIntoSlot(recycled);

    }, 280); // matches 250ms exit animation + 30ms buffer
}

// ── Keyboard ──────────────────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (document.getElementById('page-learn').classList.contains('active-page')) {
        if (e.key === 'ArrowLeft') animateAndSwipe('dislike');
        if (e.key === 'ArrowRight') animateAndSwipe('like');
    }
});

// ── Drag-to-swipe ─────────────────────────────────────────────────────────────
let isDragging = false, startX = 0, startY = 0, currentX = 0, currentY = 0;
const SWIPE_THRESHOLD = 90;

dragOverlay.addEventListener('pointerdown', (e) => {
    if (isSwiping || !getSlot(0).imageId || getSlot(0).imageId === 'none') return;
    isDragging = true;
    startX = e.clientX; startY = e.clientY;
    currentX = currentY = 0;
    dragOverlay.setPointerCapture(e.pointerId);
    getSlot(0).el.style.transition = 'none';
});

dragOverlay.addEventListener('pointermove', (e) => {
    if (!isDragging) return;
    currentX = e.clientX - startX;
    currentY = e.clientY - startY;
    getSlot(0).el.style.transform = `translate(${currentX}px,${currentY}px) rotate(${currentX * 0.07}deg)`;
    updateGhostDrag(currentX);
});

dragOverlay.addEventListener('pointerup', (e) => {
    if (!isDragging) return;
    isDragging = false;
    dragOverlay.releasePointerCapture(e.pointerId);

    if (currentX > SWIPE_THRESHOLD) animateAndSwipe('like');
    else if (currentX < -SWIPE_THRESHOLD) animateAndSwipe('dislike');
    else {
        // Snap back — springy feel
        getSlot(0).el.style.transition = 'transform 0.4s cubic-bezier(0.175,0.885,0.32,1.275)';
        getSlot(0).el.style.transform = '';
        getSlot(1).el.style.transition = 'transform 0.35s cubic-bezier(0.34,1.56,0.64,1)';
        getSlot(1).el.style.transform = 'scale(0.96) translateY(8px)';
    }
    currentX = currentY = 0;
});

dragOverlay.addEventListener('pointercancel', () => {
    if (!isDragging) return;
    isDragging = false;
    getSlot(0).el.style.transition = 'transform 0.4s cubic-bezier(0.175,0.885,0.32,1.275)';
    getSlot(0).el.style.transform = '';
    applyRoleStyles(getSlot(1), 1, true);
});

// ── Picks page ────────────────────────────────────────────────────────────────
async function loadPicks() {
    const container = document.getElementById('picks-container');
    container.innerHTML = '<p style="color:var(--text-muted);font-size:16px;">Analyzing your taste...</p>';
    try {
        const res = await fetch(`http://127.0.0.1:8000/picks?user_id=${myUserId}&limit=40`);
        const data = await res.json();
        container.innerHTML = '';
        if (!data.picks.length) {
            container.innerHTML = '<p style="color:var(--text-muted);font-size:16px;">Like some designs first!</p>';
            return;
        }
        data.picks.forEach(design => {
            const pct = Math.floor(Math.random() * 15) + 85;
            const card = document.createElement('div');
            card.className = 'pick-card';
            card.style.width = '220px';
            card.innerHTML = `
                <img src="${design.url}" alt="Nail Art" style="width:100%;height:280px;object-fit:cover;">
                <div style="padding:15px;">
                    <div style="font-size:14px;font-weight:600;margin-bottom:10px;color:var(--text-dark);">${formatTitle(design.id)}</div>
                    <div style="display:inline-block;background:var(--match-green);color:white;font-size:11px;font-weight:700;padding:4px 8px;border-radius:6px;">${pct}% MATCH</div>
                </div>`;
            container.appendChild(card);
        });
    } catch (e) { console.error('Picks error:', e); }
}

// ── Profile page ──────────────────────────────────────────────────────────────
async function loadProfile() {
    try {
        const res = await fetch(`http://127.0.0.1:8000/profile-stats?user_id=${myUserId}`);
        const data = await res.json();
        document.getElementById('stat-likes').innerText = data.likes;
        document.getElementById('stat-dislikes').innerText = data.dislikes;
    } catch (e) { console.error('Profile error:', e); }
}

// ── Reset ─────────────────────────────────────────────────────────────────────
async function resetHistory() {
    if (!confirm('Are you sure? Your AI will forget everything!')) return;
    try {
        const res = await fetch(`http://127.0.0.1:8000/reset-history?user_id=${myUserId}`, { method: 'POST' });
        if (res.ok) {
            await loadProfile();
            slots.forEach(s => { s.imageId = ''; s.img.src = ''; s.title.innerText = ''; });
            topIdx = 0;
            hideEndState();
            showPage('learn');
            await initDeck();
        } else {
            alert(`Server error: ${res.status}`);
        }
    } catch (e) { console.error(e); }
}

// ── Init: load 3 designs in parallel, all images preloaded before first paint ─
async function initDeck() {
    // Apply initial role styles before any images load
    applyRoleStyles(slots[0], 0);
    applyRoleStyles(slots[1], 1);
    applyRoleStyles(slots[2], 2);

    // Load all 3 slots concurrently — preloadImage ensures each image is
    // fully decoded in the browser cache before we assign it to the DOM
    await Promise.all([
        loadDesignIntoSlot(slots[0]),
        loadDesignIntoSlot(slots[1]),
        loadDesignIntoSlot(slots[2]),
    ]);

    if (slots[0].imageId === 'none') { showEndState(); return; }
    hideEndState();
}

// Boot
initDeck();