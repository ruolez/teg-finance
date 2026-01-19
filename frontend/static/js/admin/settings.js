// Admin Settings

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('settingsForm');
    const setup2faModal = document.getElementById('setup2faModal');

    // Save settings
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const settings = {
            site_name: document.getElementById('siteName').value,
            site_tagline: document.getElementById('siteTagline').value,
            contact_phone: document.getElementById('contactPhone').value,
            contact_email: document.getElementById('contactEmail').value,
            contact_address: document.getElementById('contactAddress').value,
            business_hours: document.getElementById('businessHours').value,
            hero_title: document.getElementById('heroTitle').value,
            hero_subtitle: document.getElementById('heroSubtitle').value,
            about_text: document.getElementById('aboutText').value,
            facebook_url: document.getElementById('facebookUrl').value,
            linkedin_url: document.getElementById('linkedinUrl').value,
            twitter_url: document.getElementById('twitterUrl').value,
            meta_description: document.getElementById('metaDescription').value,
            footer_text: document.getElementById('footerText').value
        };

        try {
            const response = await fetch('/api/admin/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (response.ok) {
                showToast('Settings saved', 'success');
            } else {
                const result = await response.json();
                showToast(result.error || 'Failed to save', 'error');
            }
        } catch (error) {
            showToast('Network error', 'error');
        }
    });

    // Setup 2FA
    const setup2faBtn = document.getElementById('setup2faBtn');
    if (setup2faBtn) {
        setup2faBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/auth/setup-2fa', {
                    method: 'POST'
                });

                const data = await response.json();

                if (response.ok) {
                    document.getElementById('qrCode').innerHTML = `<img src="${data.qr_code}" alt="QR Code">`;
                    setup2faModal.classList.add('show');
                } else {
                    showToast(data.error || 'Failed to setup 2FA', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            }
        });
    }

    // Verify 2FA
    const verify2faBtn = document.getElementById('verify2faBtn');
    if (verify2faBtn) {
        verify2faBtn.addEventListener('click', async function() {
            const code = document.getElementById('verify2faCode').value;

            if (!code || code.length !== 6) {
                showToast('Please enter a valid 6-digit code', 'error');
                return;
            }

            try {
                const response = await fetch('/api/auth/enable-2fa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });

                const data = await response.json();

                if (response.ok) {
                    showToast('2FA enabled successfully', 'success');
                    location.reload();
                } else {
                    showToast(data.error || 'Invalid code', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            }
        });
    }

    // Disable 2FA
    const disable2faBtn = document.getElementById('disable2faBtn');
    if (disable2faBtn) {
        disable2faBtn.addEventListener('click', async function() {
            const confirmed = await showConfirm(
                'Disable 2FA',
                'Are you sure you want to disable two-factor authentication? This will make your account less secure.'
            );

            if (confirmed) {
                try {
                    const response = await fetch('/api/auth/disable-2fa', {
                        method: 'POST'
                    });

                    if (response.ok) {
                        showToast('2FA disabled', 'success');
                        location.reload();
                    } else {
                        const data = await response.json();
                        showToast(data.error || 'Failed to disable 2FA', 'error');
                    }
                } catch (error) {
                    showToast('Network error', 'error');
                }
            }
        });
    }

    // Format code input
    const codeInput = document.getElementById('verify2faCode');
    if (codeInput) {
        codeInput.addEventListener('input', function() {
            this.value = this.value.replace(/[^0-9]/g, '');
        });
    }
});

function close2faModal() {
    document.getElementById('setup2faModal').classList.remove('show');
    document.getElementById('verify2faCode').value = '';
}
