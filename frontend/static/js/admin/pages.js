// Admin Pages Management

document.addEventListener('DOMContentLoaded', function() {
    // Toggle publish
    document.querySelectorAll('.toggle-publish').forEach(btn => {
        btn.addEventListener('click', async function() {
            const id = this.dataset.id;

            try {
                const response = await fetch(`/api/admin/pages/${id}/publish`, {
                    method: 'POST'
                });

                const data = await response.json();

                if (response.ok) {
                    location.reload();
                } else {
                    showToast(data.error || 'Failed to update', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            }
        });
    });

    // Delete page
    document.querySelectorAll('.delete-page').forEach(btn => {
        btn.addEventListener('click', async function() {
            const id = this.dataset.id;
            const title = this.dataset.title;

            const confirmed = await showConfirm(
                'Delete Page',
                `Are you sure you want to delete "${title}"? This action cannot be undone.`
            );

            if (confirmed) {
                try {
                    const response = await fetch(`/api/admin/pages/${id}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        showToast('Page deleted', 'success');
                        location.reload();
                    } else {
                        const data = await response.json();
                        showToast(data.error || 'Failed to delete', 'error');
                    }
                } catch (error) {
                    showToast('Network error', 'error');
                }
            }
        });
    });
});
