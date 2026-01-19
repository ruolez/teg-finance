// Admin Authentication JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const loginStep = document.getElementById('loginStep');
    const twoFactorStep = document.getElementById('twoFactorStep');
    const forgotPasswordStep = document.getElementById('forgotPasswordStep');

    const loginForm = document.getElementById('loginForm');
    const twoFactorForm = document.getElementById('twoFactorForm');
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');

    const loginBtn = document.getElementById('loginBtn');
    const verifyBtn = document.getElementById('verifyBtn');
    const forgotBtn = document.getElementById('forgotBtn');

    const loginError = document.getElementById('loginError');
    const loginErrorText = document.getElementById('loginErrorText');
    const twoFactorError = document.getElementById('twoFactorError');
    const twoFactorErrorText = document.getElementById('twoFactorErrorText');
    const forgotError = document.getElementById('forgotError');
    const forgotErrorText = document.getElementById('forgotErrorText');
    const forgotSuccess = document.getElementById('forgotSuccess');
    const forgotSuccessText = document.getElementById('forgotSuccessText');

    const forgotPasswordLink = document.getElementById('forgotPasswordLink');
    const backToLogin = document.getElementById('backToLogin');
    const backToLoginFromForgot = document.getElementById('backToLoginFromForgot');

    // Show/hide steps
    function showStep(step) {
        [loginStep, twoFactorStep, forgotPasswordStep].forEach(s => {
            s.classList.remove('active');
        });
        step.classList.add('active');
    }

    // Show error
    function showError(errorEl, textEl, message) {
        textEl.textContent = message;
        errorEl.classList.add('show');
    }

    // Hide error
    function hideError(errorEl) {
        errorEl.classList.remove('show');
    }

    // Show success
    function showSuccess(successEl, textEl, message) {
        textEl.textContent = message;
        successEl.classList.add('show');
    }

    // Set loading state
    function setLoading(btn, loading) {
        if (loading) {
            btn.classList.add('loading');
            btn.disabled = true;
        } else {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }

    // Login form submission
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        hideError(loginError);
        setLoading(loginBtn, true);

        const formData = {
            username: document.getElementById('username').value,
            password: document.getElementById('password').value
        };

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (response.ok) {
                if (data.requires_2fa) {
                    // Show 2FA step
                    document.getElementById('userId').value = data.user_id;
                    showStep(twoFactorStep);
                    document.getElementById('code').focus();
                } else if (data.redirect) {
                    window.location.href = data.redirect;
                }
            } else {
                showError(loginError, loginErrorText, data.error || 'Login failed');
            }
        } catch (error) {
            showError(loginError, loginErrorText, 'Network error. Please try again.');
        } finally {
            setLoading(loginBtn, false);
        }
    });

    // 2FA form submission
    twoFactorForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        hideError(twoFactorError);
        setLoading(verifyBtn, true);

        const formData = {
            user_id: document.getElementById('userId').value,
            code: document.getElementById('code').value
        };

        try {
            const response = await fetch('/api/auth/verify-2fa', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (response.ok && data.redirect) {
                window.location.href = data.redirect;
            } else {
                showError(twoFactorError, twoFactorErrorText, data.error || 'Verification failed');
                document.getElementById('code').value = '';
                document.getElementById('code').focus();
            }
        } catch (error) {
            showError(twoFactorError, twoFactorErrorText, 'Network error. Please try again.');
        } finally {
            setLoading(verifyBtn, false);
        }
    });

    // Forgot password form submission
    forgotPasswordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        hideError(forgotError);
        forgotSuccess.classList.remove('show');
        setLoading(forgotBtn, true);

        const formData = {
            email: document.getElementById('email').value
        };

        try {
            const response = await fetch('/api/auth/forgot-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (response.ok) {
                showSuccess(forgotSuccess, forgotSuccessText, data.message);
                forgotPasswordForm.reset();
            } else {
                showError(forgotError, forgotErrorText, data.error || 'Request failed');
            }
        } catch (error) {
            showError(forgotError, forgotErrorText, 'Network error. Please try again.');
        } finally {
            setLoading(forgotBtn, false);
        }
    });

    // Navigation links
    forgotPasswordLink.addEventListener('click', function(e) {
        e.preventDefault();
        hideError(loginError);
        showStep(forgotPasswordStep);
        document.getElementById('email').focus();
    });

    backToLogin.addEventListener('click', function() {
        hideError(twoFactorError);
        document.getElementById('code').value = '';
        showStep(loginStep);
    });

    backToLoginFromForgot.addEventListener('click', function() {
        hideError(forgotError);
        forgotSuccess.classList.remove('show');
        forgotPasswordForm.reset();
        showStep(loginStep);
    });

    // Auto-format 2FA code input (numbers only)
    document.getElementById('code').addEventListener('input', function(e) {
        this.value = this.value.replace(/[^0-9]/g, '');
    });
});
