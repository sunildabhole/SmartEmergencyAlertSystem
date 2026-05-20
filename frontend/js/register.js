/**
 * register.js – Registration with mandatory OTP verification.
 *
 * Screens:
 *   step-register → user fills form, submits
 *   step-verify   → user enters OTP received by email
 */

let regEmail = '';

document.addEventListener('DOMContentLoaded', () => {
    initOtpDigitInputs('step-verify');
    wireEvents();
});

function wireEvents() {
    document.getElementById('registerBtn').addEventListener('click', handleRegister);
    document.getElementById('verifyRegBtn').addEventListener('click', handleVerifyRegistration);
    const resendBtn = document.getElementById('resendRegOtpBtn');
    if (resendBtn) {
        resendBtn.addEventListener('click', handleResendRegOtp);
    }
}

// ── Register ──────────────────────────────────────────────────────────────────

async function handleRegister() {
    const name     = document.getElementById('name').value.trim();
    const email    = document.getElementById('email').value.trim();
    const phone    = document.getElementById('phone').value.trim();
    const password = document.getElementById('password').value;

    if (!name || !email || !password) {
        showToast('Name, email and password are required', 'error');
        return;
    }

    setButtonLoading('registerBtn', true, 'Registering…');
    try {
        const payload = { name, email, password };
        if (phone) payload.phone = phone;

        const data = await apiCall('/auth/register', 'POST', payload);
        showToast(data.message || 'Account created! Check your email for OTP.', 'success');

        regEmail = email;
        document.getElementById('regEmailLabel').textContent = email;
        document.getElementById('step-register').classList.add('hidden');
        document.getElementById('step-verify').classList.remove('hidden');
        focusFirstOtpDigit('step-verify');
        
        // Hide resend button immediately upon starting countdown
        const resendBtn = document.getElementById('resendRegOtpBtn');
        if (resendBtn) resendBtn.classList.add('hidden');
        
        startCountdown('regOtpTimer', 'resendRegOtpBtn', 300);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setButtonLoading('registerBtn', false, 'Register & Get OTP <i class="fa-solid fa-paper-plane"></i>');
    }
}

// ── Verify OTP ────────────────────────────────────────────────────────────────

async function handleVerifyRegistration() {
    const otp = collectOtp('step-verify');
    if (otp.length !== 6) { showToast('Enter the complete 6-digit OTP', 'error'); return; }

    setButtonLoading('verifyRegBtn', true, 'Verifying…');
    try {
        const data = await apiCall('/auth/verify-register', 'POST', {
            email: regEmail,
            otp_code: otp,
            purpose: 'register',
        });
        clearCountdown();
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', data.role);
        showToast('Account verified! Welcome to SEAS.', 'success');
        setTimeout(() => {
            window.location.href = data.role === 'admin' ? 'admin.html' : 'dashboard.html';
        }, 1000);
    } catch (err) {
        showToast(err.message, 'error');
        shakeOtpInputs('step-verify');
    } finally {
        setButtonLoading('verifyRegBtn', false, 'Verify & Activate <i class="fa-solid fa-check-circle"></i>');
    }
}

// ── Resend Registration OTP ───────────────────────────────────────────────────

async function handleResendRegOtp() {
    if (!regEmail) { showToast('Email not found. Please try registering again.', 'error'); return; }

    setButtonLoading('resendRegOtpBtn', true, 'Resending…');
    try {
        const data = await apiCall('/auth/request-otp', 'POST', {
            email: regEmail,
            purpose: 'register',
        });
        showToast(data.message || 'OTP resent successfully!', 'success');

        // Hide resend button upon restart
        const resendBtn = document.getElementById('resendRegOtpBtn');
        if (resendBtn) resendBtn.classList.add('hidden');

        // Restart timer
        startCountdown('regOtpTimer', 'resendRegOtpBtn', 300);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setButtonLoading('resendRegOtpBtn', false, 'Resend OTP <i class="fa-solid fa-rotate-right"></i>');
    }
}
