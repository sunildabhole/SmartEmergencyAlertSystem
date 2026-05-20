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
            else                                     resolved++;

            // Detect new pending alerts
            if (!knownAlertIds.has(alert.id) && alert.status === 'Pending') {
                newAlerts.push(alert);
            }
            knownAlertIds.add(alert.id);

            // Use live location if available, else original coords
            const lat = alert.last_latitude  ?? alert.latitude;
            const lng = alert.last_longitude ?? alert.longitude;
            const gmapsLink = `https://www.google.com/maps?q=${lat},${lng}`;

            const isLive = (alert.status === 'Pending' || alert.status === 'In Progress')
                           && alert.last_location_update;

            // GPS Accuracy Badge
            const rawAccuracy = alert.last_accuracy ?? alert.accuracy;
            let accuracyBadge = '';
            if (rawAccuracy !== null && rawAccuracy !== undefined) {
                const isAccurate = rawAccuracy <= 100;
                const accColor = isAccurate ? 'var(--success)' : 'var(--warning)';
                accuracyBadge = `<span style="display:inline-block; padding: 2px 6px; font-size: 0.7rem; border-radius: 4px; background: rgba(0,0,0,0.05); color: ${accColor}; font-weight: 600; margin-top: 4px;">
                    🎯 Accuracy: ${Math.round(rawAccuracy)}m ${isAccurate ? '' : '(Low GPS)'}
                </span>`;
            }

            // Moving Status Badge
            let movingBadge = '';
            if (isLive) {
                const isMoving = alert.is_moving;
                movingBadge = `<span style="display:inline-block; padding: 2px 6px; font-size: 0.7rem; border-radius: 4px; background: ${isMoving ? 'rgba(40,167,69,0.1)' : 'rgba(108,117,125,0.1)'}; color: ${isMoving ? 'var(--success)' : 'var(--secondary)'}; font-weight: 600; margin-top: 4px; margin-left: 4px;">
                    ${isMoving ? '🚶 Moving' : '📍 Stationary'}
                </span>`;
            }

            // Seconds/Minutes Ago Calculation
            let timeAgoText = '';
            if (isLive && alert.last_location_update) {
                const updateTime = new Date(alert.last_location_update);
                const diffMs = new Date() - updateTime;
                const diffSec = Math.max(0, Math.floor(diffMs / 1000));
                
                if (diffSec < 5) {
                    timeAgoText = 'Just now';
                } else if (diffSec < 60) {
                    timeAgoText = `${diffSec}s ago`;
                } else {
                    timeAgoText = `${Math.floor(diffSec / 60)}m ago`;
                }
            }

            const locationCell = `
                <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                    <a href="${gmapsLink}" target="_blank" class="btn btn-outline btn-small">
                        <i class="fa-solid fa-map-location-dot"></i> Map
                    </a>
                    <button onclick="navigateToCitizen(${lat}, ${lng})" class="btn btn-primary btn-small" style="padding: 0.35rem 0.6rem; font-size: 0.8rem; display: inline-flex; align-items: center; gap: 4px;">
                        <i class="fa-solid fa-diamond-turn-right"></i> Navigate
                    </button>
                </div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:6px; line-height: 1.4;">
                    <strong>Coords:</strong> ${lat.toFixed(5)}, ${lng.toFixed(5)}
                    ${isLive && alert.last_location_update
                        ? `<br><span style="color: var(--danger); font-weight: 600;"><i class="fa-solid fa-circle-dot fa-fade"></i> Live tracking</span> (${timeAgoText})`
                        : ''}
                    ${accuracyBadge ? '<br>' + accuracyBadge : ''}
                    ${movingBadge ? '<br>' + movingBadge : ''}
                </div>`;

            const statusClass = statusClassMap[alert.status] || 'status-pending';

            return `
                <tr>
                    <td>#${alert.id}</td>
                    <td>${new Date(alert.created_at).toLocaleTimeString()}</td>
                    <td>
                        <strong>${alert.user?.name ?? '—'}</strong><br>
                        <small style="color:var(--text-muted)">${alert.user?.email ?? '—'}</small>
                    </td>
                    <td><strong style="color:var(--danger)">${alert.emergency_type}</strong></td>
                    <td>${locationCell}</td>
                    <td>
                        <span class="status-badge ${statusClass}" id="status-badge-${alert.id}">
                            ${alert.status}
                        </span>
                    </td>
                    <td>
                        <select onchange="updateAlertStatus(${alert.id}, this.value)"
                                class="modern-select"
                                style="padding:0.4rem; font-size:0.85rem; width:auto;">
                            ${['Pending','In Progress','Resolved','Cancelled','False Alarm'].map(s =>
                                `<option value="${s}" ${alert.status === s ? 'selected' : ''}>${s}</option>`
                            ).join('')}
                        </select>
                    </td>
                </tr>`;
        });

        list.innerHTML = rows.join('');

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

function navigateToCitizen(lat, lng) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const originLat = position.coords.latitude;
                const originLng = position.coords.longitude;
                const url = `https://www.google.com/maps/dir/?api=1&origin=${originLat},${originLng}&destination=${lat},${lng}&travelmode=driving`;
                window.open(url, '_blank');
            },
            (error) => {
                console.warn("Could not retrieve responder GPS coordinates for navigation, using destination fallback:", error);
                const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
                window.open(url, '_blank');
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 10000 }
        );
    } else {
        const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`;
        window.open(url, '_blank');
    }
}
