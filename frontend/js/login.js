/**
 * login.js – OTP-first login with password fallback.
 *
 * Screens:
 *   step-email    → user enters email
 *   step-otp      → user enters 6-digit OTP
 *   step-password → legacy password login (optional)
 */

let registeredEmail = '';
let adminEmail = '';

document.addEventListener('DOMContentLoaded', async () => {
    initOtpDigitInputs('step-otp');
    wireEvents();
    
    // Fetch public configuration dynamically from the backend
    try {
        const config = await apiCall('/auth/config', 'GET');
        adminEmail = config.admin_email;
    } catch (err) {
        console.error('Failed to load system config, using default fallback:', err);
        adminEmail = 'sunildabhole6@gmail.com'; // Hardcoded fallback
    }
});

function wireEvents() {
    // ── Email step ──
    document.getElementById('requestOtpBtn').addEventListener('click', handleRequestOtp);
    document.getElementById('usePasswordBtn').addEventListener('click', () => {
        registeredEmail = document.getElementById('email').value.trim();
        if (!registeredEmail) { showToast('Please enter your email first', 'error'); return; }
        
        // Prevent admin from switching to the password login flow
        if (adminEmail && registeredEmail.toLowerCase() === adminEmail.toLowerCase()) {
            showToast('Admin must use OTP login.', 'error');
            return;
        }
        showStep('step-password');
    });

    // ── OTP step ──
    document.getElementById('verifyOtpBtn').addEventListener('click', handleVerifyOtp);
    document.getElementById('resendOtpBtn').addEventListener('click', handleRequestOtp);
    document.getElementById('backToEmailBtn').addEventListener('click', () => {
        clearCountdown();
        showStep('step-email');
    });

    // ── Password step ──
    document.getElementById('loginBtn').addEventListener('click', handlePasswordLogin);
    document.getElementById('backToEmailBtn2').addEventListener('click', () => showStep('step-email'));

    // Allow Enter key on email input
    document.getElementById('email').addEventListener('keydown', e => {
        if (e.key === 'Enter') handleRequestOtp();
    });
}

// ── Step visibility ────────────────────────────────────────────────────────────

function showStep(stepId) {
    ['step-email', 'step-otp', 'step-password'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });
    document.getElementById(stepId).classList.remove('hidden');
}

// ── OTP request ───────────────────────────────────────────────────────────────

async function handleRequestOtp(e) {
    registeredEmail = document.getElementById('email').value.trim();
    if (!registeredEmail) { showToast('Please enter your email', 'error'); return; }

    const isResend = e && (e.target.id === 'resendOtpBtn' || e.target.closest('#resendOtpBtn'));
    const btnId = isResend ? 'resendOtpBtn' : 'requestOtpBtn';
    const btnText = isResend ? 'Resending…' : 'Sending…';
    const origHtml = isResend 
        ? 'Resend OTP <i class="fa-solid fa-rotate-right"></i>' 
        : 'Send OTP <i class="fa-solid fa-paper-plane"></i>';

    setButtonLoading(btnId, true, btnText);
    try {
        const data = await apiCall('/auth/request-otp', 'POST', {
            email: registeredEmail,
            purpose: 'login',
        });
        showToast(data.message || 'OTP sent!', 'success');

        document.getElementById('otpEmailLabel').textContent = registeredEmail;
        showStep('step-otp');
        focusFirstOtpDigit('step-otp');
        
        // Hide resend button upon restart
        const resendBtn = document.getElementById('resendOtpBtn');
        if (resendBtn) resendBtn.classList.add('hidden');
        
        startCountdown('otpTimer', 'resendOtpBtn', 300); // 5 min
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setButtonLoading(btnId, false, origHtml);
    }
}

// ── OTP verify ────────────────────────────────────────────────────────────────

async function handleVerifyOtp() {
    const otp = collectOtp('step-otp');
    if (otp.length !== 6) { showToast('Enter the complete 6-digit OTP', 'error'); return; }

    setButtonLoading('verifyOtpBtn', true, 'Verifying…');
    try {
        const data = await apiCall('/auth/verify-otp-login', 'POST', {
            email: registeredEmail,
            otp_code: otp,
        });
        clearCountdown();
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', data.role);
        showToast('Login successful!', 'success');
        setTimeout(() => {
            window.location.href = data.role === 'admin' ? 'admin.html' : 'dashboard.html';
        }, 800);
    } catch (err) {
        showToast(err.message, 'error');
        shakeOtpInputs('step-otp');
    } finally {
        setButtonLoading('verifyOtpBtn', false, 'Verify & Login <i class="fa-solid fa-right-to-bracket"></i>');
    }
}

// ── Password login ────────────────────────────────────────────────────────────

async function handlePasswordLogin() {
    const password = document.getElementById('password').value;
    if (!password) { showToast('Enter your password', 'error'); return; }

    // Backup block to ensure admin email can never log in using a password on the frontend
    if (adminEmail && registeredEmail.toLowerCase() === adminEmail.toLowerCase()) {
        showToast('Admin must use OTP login.', 'error');
        return;
    }

    setButtonLoading('loginBtn', true, 'Logging in…');
    try {
        const data = await apiCall('/auth/login', 'POST', {
            email: registeredEmail,
            password,
        });
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', data.role);
        showToast('Login successful!', 'success');
        setTimeout(() => {
            window.location.href = data.role === 'admin' ? 'admin.html' : 'dashboard.html';
        }, 800);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setButtonLoading('loginBtn', false, 'Login <i class="fa-solid fa-right-to-bracket"></i>');
    }
}
