/**
 * admin.js – Admin dashboard with real-time alert notifications.
 *
 * Features
 * ────────
 * • Polls /admin/alerts every 5 s.
 * • Detects NEW alerts (Pending status, not seen before) since last poll.
 * • Plays an audio beep and shows a browser Notification for each new alert.
 * • "Live Map" link uses last_latitude/last_longitude when available,
 *   falling back to the original coordinates.
 * • Stat cards update every cycle.
 */

let refreshInterval   = null;
let knownAlertIds     = new Set();   // tracks IDs already displayed
let firstLoad         = true;        // suppress notification on page load
let audioCtx          = null;        // Web Audio context (created on first user gesture)

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    checkAuth(true);

    setInterval(updateClock, 1000);
    updateClock();

    document.getElementById('logoutBtn').addEventListener('click', () => {
        clearInterval(refreshInterval);
        logout();
    });

    // Request browser notification permission early
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }

    // Create AudioContext on first click (browsers require user gesture)
    document.body.addEventListener('click', initAudio, { once: true });

    fetchAdminAlerts();
    refreshInterval = setInterval(fetchAdminAlerts, 5000);
});

// ── Clock ─────────────────────────────────────────────────────────────────────

function updateClock() {
    document.getElementById('clock').innerText = new Date().toLocaleTimeString();
}

// ── Audio ─────────────────────────────────────────────────────────────────────

function initAudio() {
    try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch {
        console.warn('Web Audio not available');
    }
}

function playAlertSound() {
    if (!audioCtx) {
        try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { return; }
    }

    // Three-tone siren pattern
    const tones   = [880, 1100, 880];
    const duration = 0.18;
    let t = audioCtx.currentTime;

    tones.forEach(freq => {
        const osc  = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.type      = 'square';
        osc.frequency.setValueAtTime(freq, t);
        gain.gain.setValueAtTime(0.4, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + duration);

        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(t);
        osc.stop(t + duration);
        t += duration;
    });
}

// ── Browser notification ──────────────────────────────────────────────────────

function sendBrowserNotification(alert) {
    if (!('Notification' in window)) return;

    const show = () => {
        new Notification('🚨 New Emergency Alert!', {
            body: `${alert.emergency_type} reported by ${alert.user?.name ?? 'Unknown User'}\n` +
                  `Time: ${new Date(alert.created_at).toLocaleTimeString()}`,
            icon: 'https://cdn-icons-png.flaticon.com/512/3132/3132693.png',
            tag:  `seas-alert-${alert.id}`,
        });
    };

    if (Notification.permission === 'granted') {
        show();
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(perm => { if (perm === 'granted') show(); });
    }
}

// ── Emergency Icon Mapper ─────────────────────────────────────────────────────

function getEmergencyIcon(type) {
    const t = type ? type.toLowerCase() : '';
    if (t.includes('medical') || t.includes('health') || t.includes('heart') || t.includes('doctor')) return '🏥';
    if (t.includes('fire') || t.includes('smoke') || t.includes('burn')) return '🔥';
    if (t.includes('police') || t.includes('security') || t.includes('theft') || t.includes('robbery') || t.includes('crime') || t.includes('cop')) return '🚔';
    if (t.includes('accident') || t.includes('crash') || t.includes('road') || t.includes('vehicle')) return '🚗';
    if (t.includes('disaster') || t.includes('flood') || t.includes('earthquake') || t.includes('storm') || t.includes('tornado') || t.includes('wind') || t.includes('landslide')) return '🌪️';
    return '🚨';
}

// ── Fetch & render ────────────────────────────────────────────────────────────

async function fetchAdminAlerts() {
    try {
        const alerts = await apiCall('/admin/alerts', 'GET');
        const list   = document.getElementById('adminAlertsList');

        let pending = 0, progress = 0, resolved = 0;
        const newAlerts = [];

        const statusClassMap = {
            'Pending':    'status-pending',
            'In Progress':'status-progress',
            'Resolved':   'status-resolved',
            'Cancelled':  'status-cancelled',
            'False Alarm':'status-falsealarm',
        };

        const rows = alerts.map(alert => {
            // Count stats
            if (alert.status === 'Pending')        pending++;
            else if (alert.status === 'In Progress') progress++;
            else if (alert.status === 'Resolved')    resolved++;

            // Detect new pending alerts
            if (!knownAlertIds.has(alert.id) && alert.status === 'Pending') {
                newAlerts.push(alert);
            }
            knownAlertIds.add(alert.id);

            // Use live location if available, else original coords
            const lat = alert.last_latitude  ?? alert.latitude;
            const lng = alert.last_longitude ?? alert.longitude;
            const gmapsLink = `https://www.google.com/maps?q=${lat},${lng}`;

            // Build human-readable location card – no raw coords as primary content
            const hasAddress = alert.landmark || alert.city || alert.state || alert.postal_code || (
                alert.full_address
                && alert.full_address !== 'Address unavailable'
                && alert.full_address !== 'Address Pending / Fallback:'
            );

            let locationHtml = '';

            if (hasAddress) {
                const landmark = alert.landmark ? alert.landmark.trim() : '';
                const city = alert.city ? alert.city.trim() : '';
                const state = alert.state ? alert.state.trim() : '';
                const zip = alert.postal_code ? alert.postal_code.trim() : '';

                let mainAddress = '';
                let landmarkLine = '';

                if (landmark && city) {
                    if (landmark.toLowerCase() !== city.toLowerCase()) {
                        mainAddress = `${landmark}, ${city}`;
                    } else {
                        mainAddress = city;
                    }
                } else if (city) {
                    mainAddress = city;
                } else if (landmark) {
                    mainAddress = landmark;
                } else {
                    mainAddress = alert.full_address.split(',')[0].trim();
                }

                if (state) {
                    if (!mainAddress.toLowerCase().includes(state.toLowerCase())) {
                        mainAddress = `${mainAddress}, ${state}`;
                    }
                }

                if (landmark && landmark.toLowerCase() !== city.toLowerCase()) {
                    landmarkLine = `<div class="loc-landmark">Near ${landmark}</div>`;
                }

                locationHtml = `
                    <div class="location-card">
                        <div class="loc-address">📍 ${mainAddress}</div>
                        ${landmarkLine}
                        ${zip ? `<div class="loc-zip">${zip}</div>` : ''}
                        <details class="gps-details">
                            <summary>Advanced GPS Details</summary>
                            <span>${lat.toFixed(6)}, ${lng.toFixed(6)}</span>
                        </details>
                    </div>
                `;
            } else {
                locationHtml = `
                    <div class="location-card">
                        <div class="loc-address" style="color: var(--text-muted); font-weight: 600;">📍 GPS Coordinates Only</div>
                        <div class="loc-landmark" style="font-weight: 700; color: var(--text-main); font-size: 0.95rem; margin-top: 2px;">
                            ${lat.toFixed(6)}, ${lng.toFixed(6)}
                        </div>
                        <div class="loc-zip" style="font-size: 0.75rem; color: var(--danger); font-weight: 600; margin-top: 4px;">
                            No address details recorded
                        </div>
                    </div>
                `;
            }

            const statusClass = statusClassMap[alert.status] || 'status-pending';

            // Unified Actions Cell
            const actionsCell = `
                <td>
                    <div class="actions-wrapper">
                        <div class="btn-group">
                            <a href="${gmapsLink}" target="_blank" class="btn btn-outline btn-xsmall">
                                <i class="fa-solid fa-map-location-dot"></i> View Map
                            </a>
                            <button onclick="navigateToCitizen(${lat}, ${lng}, '${encodeURIComponent(alert.city || '')}', '${encodeURIComponent(alert.state || '')}')" class="btn btn-primary btn-xsmall">
                                <i class="fa-solid fa-location-arrow"></i> Navigate
                            </button>
                        </div>
                        <div class="status-meta">
                            <span class="status-badge ${statusClass}" id="status-badge-${alert.id}">
                                ${alert.status}
                            </span>
                            <select onchange="updateAlertStatus(${alert.id}, this.value)"
                                    class="select-xsmall"
                                    id="status-select-${alert.id}">
                                ${['Pending','In Progress','Resolved','Cancelled','False Alarm'].map(s =>
                                    `<option value="${s}" ${alert.status === s ? 'selected' : ''}>${s}</option>`
                                ).join('')}
                            </select>
                        </div>
                    </div>
                </td>
            `;

            return `
                <tr>
                    <td>#${alert.id}</td>
                    <td>${new Date(alert.created_at).toLocaleTimeString()}</td>
                    <td>
                        <span class="citizen-name">${alert.user?.name ?? '—'}</span>
                        <span class="citizen-email">${alert.user?.email ?? '—'}</span>
                    </td>
                    <td>
                        <span class="emergency-badge">
                            ${getEmergencyIcon(alert.emergency_type)} ${alert.emergency_type}
                        </span>
                    </td>
                    <td>${locationHtml}</td>
                    ${actionsCell}
                </tr>`;
        });

        // Track active focus to avoid layout jumps or interruptions during background polling
        const activeElementId = document.activeElement ? document.activeElement.id : null;
        
        list.innerHTML = rows.join('');
        
        if (activeElementId) {
            const el = document.getElementById(activeElementId);
            if (el) el.focus();
        }

        document.getElementById('statPending').innerText  = pending;
        document.getElementById('statProgress').innerText = progress;
        document.getElementById('statResolved').innerText = resolved;

        // ── Notify admin of new alerts (skip on first load) ──
        if (!firstLoad && newAlerts.length > 0) {
            newAlerts.forEach(a => {
                playAlertSound();
                sendBrowserNotification(a);
                showToast(
                    `🚨 New ${a.emergency_type} alert from ${a.user?.name ?? 'Unknown'}`,
                    'error'
                );
            });
        }

        firstLoad = false;
    } catch (err) {
        console.error('Failed to fetch admin alerts', err);
    }
}

// ── Update status ─────────────────────────────────────────────────────────────

async function updateAlertStatus(alertId, newStatus) {
    try {
        await apiCall(`/admin/alerts/${alertId}`, 'PUT', { status: newStatus });
        showToast(`Alert #${alertId} → ${newStatus}`, 'success');

        const statusClassMap = {
            'Pending':    'status-pending',
            'In Progress':'status-progress',
            'Resolved':   'status-resolved',
            'Cancelled':  'status-cancelled',
            'False Alarm':'status-falsealarm',
        };

        const badge = document.getElementById(`status-badge-${alertId}`);
        if (badge) {
            badge.innerText   = newStatus;
            badge.className   = `status-badge ${statusClassMap[newStatus]}`;
        }

        fetchAdminAlerts();
    } catch {
        showToast('Failed to update status', 'error');
    }
}

// ── Navigate to Citizen (Google Maps Driving Route) ───────────────────────────

function navigateToCitizen(lat, lng, city = '', state = '') {
    const decodedCity = city ? decodeURIComponent(city) : '';
    const decodedState = state ? decodeURIComponent(state) : '';
    const destSuffix = (decodedCity || decodedState) ? ` (${[decodedCity, decodedState].filter(Boolean).join(', ')})` : '';
    const destinationQuery = `${lat},${lng}${destSuffix}`;
    const encodedDestination = encodeURIComponent(destinationQuery);
    
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const originLat = position.coords.latitude;
                const originLng = position.coords.longitude;
                const url = `https://www.google.com/maps/dir/?api=1&origin=${originLat},${originLng}&destination=${encodedDestination}&travelmode=driving`;
                window.open(url, '_blank');
            },
            (error) => {
                console.warn("Could not retrieve responder GPS coordinates for navigation, using destination fallback:", error);
                const url = `https://www.google.com/maps/dir/?api=1&destination=${encodedDestination}&travelmode=driving`;
                window.open(url, '_blank');
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 10000 }
        );
    } else {
        const url = `https://www.google.com/maps/dir/?api=1&destination=${encodedDestination}&travelmode=driving`;
        window.open(url, '_blank');
    }
}
