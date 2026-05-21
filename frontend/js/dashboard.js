/**
 * dashboard.js – user dashboard with live location tracking.
 *
 * After an SOS alert is created, the browser watches the device position
 * (watchPosition) and PUTs updates to /alerts/{id}/location every
 * LOCATION_UPDATE_INTERVAL ms while the alert is active.
 *
 * Tracking stops automatically when the user cancels the alert or when
 * the alert status changes to Resolved / Cancelled / False Alarm.
 */

const LOCATION_UPDATE_INTERVAL = 10_000; // 10 seconds

let activeAlertId  = null;   // currently tracked alert ID
let watchId        = null;   // navigator.geolocation.watchPosition handle
let locationTimer  = null;   // setInterval handle for location PUTs
let lastPosition   = null;   // most recent GeolocationPosition
let isSendingSOS   = false;  // Protect against duplicate SOS triggers


document.addEventListener('DOMContentLoaded', () => {
    checkAuth(false);
    fetchUserInfo();
    fetchMyAlerts();

    document.getElementById('logoutBtn').addEventListener('click', stopTrackingAndLogout);
    document.getElementById('sosBtn').addEventListener('click', sendSOS);
});

// ── Logout ────────────────────────────────────────────────────────────────────

function stopTrackingAndLogout() {
    stopLiveTracking();
    logout();
}

// ── User info ─────────────────────────────────────────────────────────────────

async function fetchUserInfo() {
    try {
        const user = await apiCall('/auth/me', 'GET');
        document.getElementById('userName').innerText = `Hello, ${user.name}`;
    } catch {
        showToast('Failed to fetch user info', 'error');
    }
}

// ── SOS ───────────────────────────────────────────────────────────────────────

async function sendSOS() {
    if (isSendingSOS) return;

    // Check if the user already has an active emergency alert tracked locally
    if (activeAlertId) {
        showToast('You already have an active emergency.', 'warning');
        return;
    }

    const emergencyType = document.getElementById('emergencyType').value;
    const statusText    = document.getElementById('locationStatus');

    if (!navigator.geolocation) {
        showToast('Your browser does not support location tracking.', 'error');
        return;
    }

    // HTTPS / Secure Context Validation
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const isSecure = window.location.protocol === 'https:' || isLocalhost;
    if (!isSecure) {
        showToast('Browser blocks location access on insecure HTTP connections. Please use HTTPS or localhost.', 'error');
        console.warn('Geolocation blocked: Insecure context detected.');
        return;
    }

    isSendingSOS = true;

    // Disable button and adapt styles
    const sosBtn = document.getElementById('sosBtn');
    sosBtn.disabled = true;
    sosBtn.classList.add('sos-active');

    const sosText = sosBtn.querySelector('.sos-text');
    const originalText = 'SOS';
    const originalFontSize = '';

    if (sosText) {
        sosText.textContent = "📡 CAPTURING";
        sosText.style.fontSize = "1.1rem"; // scale down to fit inside the circular button beautifully
    }

    toggleLoader(true, 'Getting precise location…');
    statusText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Acquiring GPS…';

    let retryAttempted = false;

    function acquirePosition() {
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const { latitude, longitude, accuracy } = position.coords;

                // Client-side coordinates validation
                if (!latitude || !longitude || latitude === 0 || longitude === 0 || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
                    console.error("Invalid coordinates fetched:", latitude, longitude);
                    handleFailure({ code: 0, message: "Invalid coordinates received." });
                    return;
                }

                console.info("Location fetched successfully", { latitude, longitude, accuracy });
                lastPosition = position;

                // Accuracy Warning (still allows SOS)
                if (accuracy && accuracy > 100) {
                    showToast('Low GPS accuracy detected. Move to an open area.', 'warning');
                }

                toggleLoader(true, 'Sending SOS Alert…');
                statusText.innerHTML = '<i class="fa-solid fa-satellite-dish"></i> Transmitting signal…';
                if (sosText) {
                    sosText.textContent = "🚨 TRANSMITTING";
                    sosText.style.fontSize = "1.0rem";
                }

                try {
                    const alert = await apiCall('/alerts/', 'POST', {
                        emergency_type: emergencyType,
                        latitude,
                        longitude,
                        accuracy: accuracy || null
                    });

                    activeAlertId = alert.id;
                    toggleLoader(false);
                    showToast('EMERGENCY ALERT SENT SUCCESSFULLY!', 'success');

                    // Show clean location immediately using alert response
                    updateLocationStatusDot(latitude, longitude, accuracy, alert);

                    // Begin live-location streaming
                    startLiveTracking(alert.id);
                    fetchMyAlerts();
                } catch (err) {
                    toggleLoader(false);
                    showToast(err.message || 'Failed to send alert', 'error');
                    statusText.innerHTML = '<i class="fa-solid fa-xmark" style="color:var(--danger)"></i> Failed to send';
                    resetSosButton();
                } finally {
                    isSendingSOS = false;
                }
            },
            (error) => {
                console.warn(`Geolocation attempt failed (retry attempted: ${retryAttempted}):`, error);

                // Attempt one automatic retry if not tried yet
                if (!retryAttempted) {
                    retryAttempted = true;
                    console.info("Attempting automatic retry to warm up GPS...");
                    toggleLoader(true, 'Retrying location capture…');
                    statusText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Retrying GPS capture…';
                    acquirePosition();
                    return;
                }

                // Handle final failure after retry
                handleFailure(error);
            },
            { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 } // strict WhatsApp high accuracy options
        );
    }

    function handleFailure(error) {
        let userMessage = "Could not detect location.";
        if (error && error.code) {
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    userMessage = "Location access denied. Please allow GPS permission.";
                    break;
                case error.POSITION_UNAVAILABLE:
                    userMessage = "Unable to detect location.";
                    break;
                case error.TIMEOUT:
                    userMessage = "Location request timed out.";
                    break;
            }
        } else if (error && error.message) {
            userMessage = error.message;
        }

        toggleLoader(false);
        showToast(userMessage, 'error');
        statusText.innerHTML = `<i class="fa-solid fa-location-xmark" style="color:var(--danger)"></i> ${userMessage}`;
        resetSosButton();
        isSendingSOS = false;
    }

    function resetSosButton() {
        sosBtn.disabled = false;
        if (sosText) {
            sosText.textContent = originalText;
            sosText.style.fontSize = originalFontSize;
        }
    }

    // Start location capture flow
    acquirePosition();
}

// ── Live Location Tracking ────────────────────────────────────────────────────

function startLiveTracking(alertId) {
    stopLiveTracking(); // clear any previous watch

    // Continuously watch device position (WhatsApp style)
    watchId = navigator.geolocation.watchPosition(
        (pos) => { 
            // Validate fresh position and log accuracy
            if (pos.coords.accuracy > 100) {
                console.warn(`Low GPS accuracy in live tracking: ${pos.coords.accuracy}m`);
            }
            lastPosition = pos; 
        },
        (err) => console.warn('watchPosition error:', err.message),
        { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 } // high accuracy, no cache
    );

    // Push location to server every LOCATION_UPDATE_INTERVAL ms
    locationTimer = setInterval(async () => {
        if (!lastPosition || !activeAlertId) return;

        const { latitude, longitude, accuracy } = lastPosition.coords;
        try {
            // Using the professional PATCH /alerts/location/{id} endpoint
            const alert = await apiCall(`/alerts/location/${activeAlertId}`, 'PATCH', { 
                latitude, 
                longitude,
                accuracy: accuracy || null 
            });
            updateLocationStatusDot(latitude, longitude, accuracy, alert);
        } catch (err) {
            // Non-fatal – alert may have been resolved on server
            if (err.message.includes('400') || err.message.includes('404')) {
                stopLiveTracking();
            }
            console.warn('Location update failed:', err.message);
        }
    }, LOCATION_UPDATE_INTERVAL);
}

function stopLiveTracking() {
    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }
    if (locationTimer !== null) {
        clearInterval(locationTimer);
        locationTimer = null;
    }
    activeAlertId = null;
}

function updateLocationStatusDot(lat, lng, accuracy, alert = null) {
    const statusText = document.getElementById('locationStatus');
    if (!statusText) return;

    const hasAddress = alert && (
        alert.city || 
        alert.landmark || 
        (alert.full_address && alert.full_address !== 'Address unavailable' && alert.full_address !== 'Address Pending / Fallback:')
    );

    if (hasAddress) {
        let cleanName = '';
        const landmark = alert.landmark ? alert.landmark.trim() : '';
        const city = alert.city ? alert.city.trim() : '';
        const state = alert.state ? alert.state.trim() : '';

        if (landmark && city) {
            if (landmark.toLowerCase() !== city.toLowerCase()) {
                cleanName = `${landmark}, ${city}`;
            } else {
                cleanName = landmark;
            }
        } else if (landmark) {
            cleanName = landmark;
        } else if (city) {
            cleanName = city;
        }

        if (state) {
            if (cleanName) {
                if (!cleanName.toLowerCase().includes(state.toLowerCase())) {
                    cleanName = `${cleanName}, ${state}`;
                }
            } else {
                cleanName = state;
            }
        }

        if (!cleanName && alert.full_address) {
            cleanName = alert.full_address.split(',').slice(0, 2).join(', ').trim();
        }

        statusText.innerHTML = `
            <div style="font-weight: 700; color: var(--secondary); font-size: 1.1rem; margin-top: 4px;">📍 Live Location Active</div>
            <div style="font-weight: 600; color: var(--text-main); font-size: 0.95rem; margin-top: 2px;">${cleanName}</div>
            <div style="font-size: 0.8rem; color: var(--success); font-weight: 700; margin-top: 4px;">
                <i class="fa-solid fa-circle-check"></i> ✓ Location verified
            </div>
        `;
    } else if (alert) {
        statusText.innerHTML = `
            <div style="font-weight: 700; color: var(--secondary); font-size: 1.1rem; margin-top: 4px;">📍 Live Location Active</div>
            <div style="font-weight: 600; color: var(--text-muted); font-size: 0.9rem; margin-top: 2px;">GPS: ${lat.toFixed(6)}, ${lng.toFixed(6)}</div>
            <div style="font-size: 0.8rem; color: var(--success); font-weight: 700; margin-top: 4px;">
                <i class="fa-solid fa-circle-check"></i> ✓ GPS Signal verified
            </div>
        `;
    } else {
        statusText.innerHTML = `
            <div style="font-weight: 700; color: var(--danger); font-size: 1.1rem; margin-top: 4px;">📍 Live Location Captured</div>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 2px; font-style: italic;">Acquiring signal...</div>
        `;
    }
}

// ── My Alerts ─────────────────────────────────────────────────────────────────

async function fetchMyAlerts() {
    try {
        const alerts = await apiCall('/alerts/my-alerts', 'GET');
        const list = document.getElementById('alertsList');

        // Restore active alert tracking if found in the list on initial load or refresh
        const activeAlert = alerts.find(a => a.status === 'Pending' || a.status === 'In Progress');
        if (activeAlert) {
            if (!activeAlertId) {
                activeAlertId = activeAlert.id;
                startLiveTracking(activeAlert.id);
            }
            const statusText = document.getElementById('locationStatus');
            if (statusText) {
                const lat = activeAlert.last_latitude ?? activeAlert.latitude;
                const lng = activeAlert.last_longitude ?? activeAlert.longitude;
                const accuracy = activeAlert.last_accuracy ?? activeAlert.accuracy;
                updateLocationStatusDot(lat, lng, accuracy, activeAlert);
            }
            // Ensure the SOS button is disabled because there is already an active alert
            const sosBtn = document.getElementById('sosBtn');
            sosBtn.disabled = true;
            sosBtn.classList.add('sos-active');
            const sosText = sosBtn.querySelector('.sos-text');
            if (sosText) {
                sosText.textContent = "🛰 ACTIVE";
                sosText.style.fontSize = "1.2rem";
            }
        } else {
            // No active alert found, ensure button is active and activeAlertId is cleared
            if (activeAlertId) {
                stopLiveTracking();
                const statusText = document.getElementById('locationStatus');
                if (statusText) {
                    statusText.innerHTML = '<i class="fa-solid fa-location-dot"></i> Ready to capture location';
                }
            }
            const sosBtn = document.getElementById('sosBtn');
            sosBtn.disabled = false;
            sosBtn.classList.remove('sos-active');
            const sosText = sosBtn.querySelector('.sos-text');
            if (sosText) {
                sosText.textContent = "SOS";
                sosText.style.fontSize = "";
            }
        }

        if (alerts.length === 0) {
            list.innerHTML = '<p class="text-muted" style="text-align:center; padding: 1rem;">No recent alerts.</p>';
            return;
        }

        const statusClassMap = {
            'Pending':    'status-pending',
            'In Progress':'status-progress',
            'Resolved':   'status-resolved',
            'Cancelled':  'status-cancelled',
            'False Alarm':'status-falsealarm',
        };

        list.innerHTML = alerts.map(alert => {
            const isActive = alert.status === 'Pending' || alert.status === 'In Progress';

            // Show live-location link if we have a recent position
            const locLat = alert.last_latitude  ?? alert.latitude;
            const locLng = alert.last_longitude ?? alert.longitude;
            const gmapsLink = `https://www.google.com/maps?q=${locLat},${locLng}`;
            const liveTag   = isActive
                ? `<span class="live-badge"><i class="fa-solid fa-circle-dot"></i> LIVE</span>`
                : '';

            return `
            <div style="padding:15px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; gap:10px;">
                <div style="flex:1;">
                    <strong style="font-size:1.1rem; color:var(--secondary);">${alert.emergency_type}</strong>
                    ${liveTag}
                    <div style="font-size:0.85rem; color:var(--text-muted); margin-top:4px;">
                        ${new Date(alert.created_at).toLocaleString()}
                    </div>
                    <div style="margin-top:6px;">
                        <a href="${gmapsLink}" target="_blank" class="btn btn-outline btn-small" style="font-size:0.8rem;">
                            <i class="fa-solid fa-map-location-dot"></i> ${isActive ? 'Live Map' : 'View Map'}
                        </a>
                    </div>
                </div>
                <div style="text-align:right;">
                    <span class="status-badge ${statusClassMap[alert.status] || 'status-pending'}">${alert.status}</span>
                    ${alert.status === 'Pending' ? `
                    <div style="margin-top:8px;">
                        <button onclick="cancelUserAlert(${alert.id})" class="btn btn-outline btn-small"
                            style="font-size:0.75rem; color:var(--text-muted); border-color:#ccc;">
                            Cancel Alert
                        </button>
                    </div>` : ''}
                </div>
            </div>`;
        }).join('');

        // If the active alert has moved to a terminal state, stop tracking
        if (activeAlertId) {
            const activeAlert = alerts.find(a => a.id === activeAlertId);
            if (activeAlert && !['Pending', 'In Progress'].includes(activeAlert.status)) {
                stopLiveTracking();
                const statusText = document.getElementById('locationStatus');
                if (statusText) {
                    statusText.innerHTML =
                        '<i class="fa-solid fa-check" style="color:var(--success)"></i> Alert resolved – tracking stopped';
                }
                const sosBtn = document.getElementById('sosBtn');
                sosBtn.disabled = false;
                sosBtn.classList.remove('sos-active');
                const sosText = sosBtn.querySelector('.sos-text');
                if (sosText) {
                    sosText.textContent = "SOS";
                    sosText.style.fontSize = "";
                }
            }
        }
    } catch (err) {
        console.error('Failed to fetch alerts', err);
    }
}

// ── Cancel Alert ──────────────────────────────────────────────────────────────

async function cancelUserAlert(alertId) {
    if (!confirm('Are you sure you want to cancel this emergency alert?')) return;

    toggleLoader(true, 'Cancelling alert…');
    try {
        await apiCall(`/alerts/cancel/${alertId}`, 'PUT');
        toggleLoader(false);
        showToast('Alert Cancelled Successfully', 'success');

        if (activeAlertId === alertId) {
            stopLiveTracking();
            document.getElementById('locationStatus').innerHTML =
                '<i class="fa-solid fa-location-dot"></i> Ready to capture location';
            const sosBtn = document.getElementById('sosBtn');
            sosBtn.disabled = false;
            sosBtn.classList.remove('sos-active');
            const sosText = sosBtn.querySelector('.sos-text');
            if (sosText) {
                sosText.textContent = "SOS";
                sosText.style.fontSize = "";
            }
        }

        fetchMyAlerts();
    } catch (err) {
        toggleLoader(false);
        showToast(err.message, 'error');
    }
}
