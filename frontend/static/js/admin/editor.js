// Admin Page Editor with Quill

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Quill editor
    const quill = new Quill('#editor', {
        theme: 'snow',
        modules: {
            toolbar: [
                [{ 'header': [1, 2, 3, 4, 5, 6, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                [{ 'indent': '-1'}, { 'indent': '+1' }],
                ['link', 'image'],
                ['blockquote', 'code-block'],
                ['clean']
            ]
        },
        placeholder: 'Start writing your content...'
    });

    // Form elements
    const form = document.getElementById('pageForm');
    const titleInput = document.getElementById('title');
    const slugInput = document.getElementById('slug');
    const isServicePage = document.getElementById('isServicePage');
    const serviceOptions = document.getElementById('serviceOptions');
    const slugPrefix = document.querySelector('.slug-prefix');

    // Auto-generate slug from title
    titleInput.addEventListener('input', function() {
        if (!document.getElementById('pageId').value) {
            slugInput.value = generateSlug(this.value);
        }
    });

    // Validate slug format
    slugInput.addEventListener('input', function() {
        this.value = generateSlug(this.value);
    });

    // Toggle service page options
    isServicePage.addEventListener('change', function() {
        serviceOptions.style.display = this.checked ? 'block' : 'none';
        slugPrefix.textContent = this.checked ? '/services/' : '/';
    });

    // Image picker
    const imagePickerModal = document.getElementById('imagePickerModal');
    const selectHeroBtn = document.getElementById('selectHeroBtn');
    const heroPreview = document.getElementById('heroPreview');
    const heroImageId = document.getElementById('heroImageId');

    selectHeroBtn.addEventListener('click', function() {
        imagePickerModal.classList.add('show');
    });

    document.querySelectorAll('.image-item').forEach(item => {
        item.addEventListener('click', function() {
            const id = this.dataset.id;
            const filename = this.dataset.filename;

            heroImageId.value = id;
            heroPreview.innerHTML = `<img src="/uploads/${filename}" alt="Hero image">`;
            closeImagePicker();
        });
    });

    // Form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const pageId = document.getElementById('pageId').value;
        const isNew = !pageId;

        // Get content from Quill
        const content = quill.root.innerHTML;

        const data = {
            title: titleInput.value,
            slug: slugInput.value,
            content: content,
            meta_title: document.getElementById('metaTitle').value,
            meta_description: document.getElementById('metaDescription').value,
            is_published: document.getElementById('isPublished').checked,
            is_service_page: isServicePage.checked,
            service_icon: document.getElementById('serviceIcon').value || null,
            service_order: parseInt(document.getElementById('serviceOrder').value) || 0,
            hero_image_id: heroImageId.value || null
        };

        try {
            const url = isNew ? '/api/admin/pages' : `/api/admin/pages/${pageId}`;
            const method = isNew ? 'POST' : 'PUT';

            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                showToast(isNew ? 'Page created' : 'Page saved', 'success');

                if (isNew && result.page) {
                    window.location.href = `/admin/pages/${result.page.id}`;
                }
            } else {
                showToast(result.error || 'Failed to save', 'error');
            }
        } catch (error) {
            showToast('Network error', 'error');
        }
    });

    function generateSlug(text) {
        return text
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .replace(/^-|-$/g, '');
    }
});

function closeImagePicker() {
    document.getElementById('imagePickerModal').classList.remove('show');
}
