// ── Toast Notifications ───────────────────────────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? 'fa-check-circle'
               : type === 'error'   ? 'fa-exclamation-circle'
               :                      'fa-info-circle';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ── Loader ────────────────────────────────────────────────────────────────────

function toggleLoader(show, text = 'Loading…') {
    const loader = document.getElementById('loader-overlay');
    if (!loader) return;
    if (show) {
        loader.querySelector('p').innerText = text;
        loader.classList.remove('hidden');
    } else {
        loader.classList.add('hidden');
    }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

function checkAuth(requireAdmin = false) {
    const token = localStorage.getItem('token');
    const role  = localStorage.getItem('role');
    if (!token) { window.location.href = 'login.html'; return null; }
    if (requireAdmin && role !== 'admin') { window.location.href = 'dashboard.html'; return null; }
    return { token, role };
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    window.location.href = 'login.html';
}

// ── Button loading state ──────────────────────────────────────────────────────

function setButtonLoading(id, loading, originalHtml = '') {
    const btn = document.getElementById(id);
    if (!btn) return;
    if (loading) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ' + (originalHtml || '');
    } else {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

// ── OTP digit input helpers ───────────────────────────────────────────────────

/**
 * Wire up 6 individual OTP digit boxes inside a container.
 * Auto-advances focus, supports backspace, paste.
 */
function initOtpDigitInputs(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const digits = container.querySelectorAll('.otp-digit');

    digits.forEach((input, index) => {
        input.addEventListener('input', (e) => {
            const val = e.target.value.replace(/\D/g, '');
            e.target.value = val.slice(-1); // keep last digit only
            if (val && index < digits.length - 1) {
                digits[index + 1].focus();
            }
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !e.target.value && index > 0) {
                digits[index - 1].focus();
            }
        });

        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData)
                .getData('text')
                .replace(/\D/g, '')
                .slice(0, 6);
            pasted.split('').forEach((ch, i) => {
                if (digits[i]) digits[i].value = ch;
            });
            const next = Math.min(pasted.length, digits.length - 1);
            digits[next].focus();
        });
    });
}

/** Read the 6-digit OTP from all digit boxes inside a container. */
function collectOtp(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return '';
    return [...container.querySelectorAll('.otp-digit')]
        .map(i => i.value)
        .join('');
}

/** Focus the first OTP digit inside a container. */
function focusFirstOtpDigit(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const first = container.querySelector('.otp-digit');
    if (first) first.focus();
}

/** Shake animation on wrong OTP. */
function shakeOtpInputs(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const row = container.querySelector('.otp-input-row');
    if (!row) return;
    row.classList.add('shake');
    setTimeout(() => row.classList.remove('shake'), 500);
}

// ── OTP Countdown Timer ───────────────────────────────────────────────────────

let countdownInterval = null;

/**
 * @param {string} timerElId    – element to show "Expires in M:SS"
 * @param {string|null} resendElId – button to show when timer hits 0
 * @param {number} seconds      – countdown duration
 */
function startCountdown(timerElId, resendElId, seconds) {
    clearCountdown();
    let remaining = seconds;

    const timerEl  = document.getElementById(timerElId);
    const resendEl = resendElId ? document.getElementById(resendElId) : null;

    if (resendEl) resendEl.classList.add('hidden');

    const tick = () => {
        if (!timerEl) return;
        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        timerEl.textContent = `OTP expires in ${m}:${String(s).padStart(2, '0')}`;
        if (remaining <= 0) {
            clearCountdown();
            timerEl.textContent = 'OTP expired. Please request a new one.';
            timerEl.style.color = 'var(--danger)';
            if (resendEl) resendEl.classList.remove('hidden');
        }
        remaining--;
    };

    tick();
    countdownInterval = setInterval(tick, 1000);
}

function clearCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
}
