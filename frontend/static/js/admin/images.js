// Admin Image Management

document.addEventListener('DOMContentLoaded', function() {
    const uploadModal = document.getElementById('uploadModal');
    const editModal = document.getElementById('editModal');
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadPreview = document.getElementById('uploadPreview');
    const previewImage = document.getElementById('previewImage');
    const uploadSubmit = document.getElementById('uploadSubmit');

    let selectedFile = null;

    // Open upload modal
    document.getElementById('uploadBtn').addEventListener('click', () => {
        uploadModal.classList.add('show');
    });

    const uploadBtnEmpty = document.getElementById('uploadBtnEmpty');
    if (uploadBtnEmpty) {
        uploadBtnEmpty.addEventListener('click', () => {
            uploadModal.classList.add('show');
        });
    }

    // Upload area click
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFile(fileInput.files[0]);
        }
    });

    function handleFile(file) {
        // Validate file type
        const allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            showToast('Invalid file type. Please upload PNG, JPG, GIF, or WebP.', 'error');
            return;
        }

        // Validate file size (5MB)
        if (file.size > 5 * 1024 * 1024) {
            showToast('File too large. Maximum size is 5MB.', 'error');
            return;
        }

        selectedFile = file;

        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            uploadArea.style.display = 'none';
            uploadPreview.style.display = 'block';
            uploadSubmit.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    // Upload submit
    uploadSubmit.addEventListener('click', async () => {
        if (!selectedFile) return;

        uploadSubmit.disabled = true;
        uploadSubmit.innerHTML = '<span class="material-icons">hourglass_empty</span> Uploading...';

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('alt_text', document.getElementById('altText').value);

        try {
            const response = await fetch('/api/admin/images', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                showToast('Image uploaded', 'success');
                location.reload();
            } else {
                showToast(result.error || 'Upload failed', 'error');
            }
        } catch (error) {
            showToast('Network error', 'error');
        } finally {
            uploadSubmit.disabled = false;
            uploadSubmit.innerHTML = '<span class="material-icons">cloud_upload</span> Upload';
        }
    });

    // Copy URL
    document.querySelectorAll('.copy-url').forEach(btn => {
        btn.addEventListener('click', function() {
            const filename = this.dataset.filename;
            const url = `${window.location.origin}/uploads/${filename}`;

            navigator.clipboard.writeText(url).then(() => {
                showToast('URL copied to clipboard', 'success');
            }).catch(() => {
                showToast('Failed to copy URL', 'error');
            });
        });
    });

    // Edit image
    document.querySelectorAll('.edit-image').forEach(btn => {
        btn.addEventListener('click', function() {
            document.getElementById('editImageId').value = this.dataset.id;
            document.getElementById('editAltText').value = this.dataset.alt || '';
            editModal.classList.add('show');
        });
    });

    // Edit submit
    document.getElementById('editSubmit').addEventListener('click', async () => {
        const id = document.getElementById('editImageId').value;
        const altText = document.getElementById('editAltText').value;

        try {
            const response = await fetch(`/api/admin/images/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ alt_text: altText })
            });

            if (response.ok) {
                showToast('Image updated', 'success');
                location.reload();
            } else {
                const result = await response.json();
                showToast(result.error || 'Update failed', 'error');
            }
        } catch (error) {
            showToast('Network error', 'error');
        }
    });

    // Delete image
    document.querySelectorAll('.delete-image').forEach(btn => {
        btn.addEventListener('click', async function() {
            const id = this.dataset.id;
            const name = this.dataset.name;

            const confirmed = await showConfirm(
                'Delete Image',
                `Are you sure you want to delete "${name}"? This action cannot be undone.`
            );

            if (confirmed) {
                try {
                    const response = await fetch(`/api/admin/images/${id}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        showToast('Image deleted', 'success');
                        location.reload();
                    } else {
                        const result = await response.json();
                        showToast(result.error || 'Delete failed', 'error');
                    }
                } catch (error) {
                    showToast('Network error', 'error');
                }
            }
        });
    });
});

function closeUploadModal() {
    document.getElementById('uploadModal').classList.remove('show');
    clearPreview();
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('show');
}

function clearPreview() {
    document.getElementById('uploadArea').style.display = '';
    document.getElementById('uploadPreview').style.display = 'none';
    document.getElementById('fileInput').value = '';
    document.getElementById('altText').value = '';
    document.getElementById('uploadSubmit').disabled = true;
}
