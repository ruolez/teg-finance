// Admin Navigation Management

document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('navModal');
    const navType = document.getElementById('navType');
    const urlGroup = document.getElementById('urlGroup');
    const pageGroup = document.getElementById('pageGroup');
    const navItemsList = document.getElementById('navItemsList');

    // Add item button
    document.getElementById('addItemBtn').addEventListener('click', () => {
        document.getElementById('navModalTitle').textContent = 'Add Menu Item';
        document.getElementById('navItemId').value = '';
        document.getElementById('navLabel').value = '';
        document.getElementById('navType').value = 'custom';
        document.getElementById('navUrl').value = '';
        document.getElementById('navPageId').value = '';
        document.getElementById('navParentId').value = '';
        document.getElementById('navVisible').checked = true;
        document.getElementById('navNewTab').checked = false;

        urlGroup.style.display = '';
        pageGroup.style.display = 'none';

        modal.classList.add('show');
    });

    // Toggle URL/Page fields
    navType.addEventListener('change', function() {
        if (this.value === 'custom') {
            urlGroup.style.display = '';
            pageGroup.style.display = 'none';
        } else {
            urlGroup.style.display = 'none';
            pageGroup.style.display = '';
        }
    });

    // Edit item
    document.querySelectorAll('.edit-nav-item').forEach(btn => {
        btn.addEventListener('click', function() {
            const item = JSON.parse(this.dataset.item);

            document.getElementById('navModalTitle').textContent = 'Edit Menu Item';
            document.getElementById('navItemId').value = item.id;
            document.getElementById('navLabel').value = item.label;
            document.getElementById('navVisible').checked = item.is_visible;
            document.getElementById('navNewTab').checked = item.open_in_new_tab;
            document.getElementById('navParentId').value = item.parent_id || '';

            if (item.page_id) {
                document.getElementById('navType').value = 'page';
                document.getElementById('navPageId').value = item.page_id;
                document.getElementById('navUrl').value = '';
                urlGroup.style.display = 'none';
                pageGroup.style.display = '';
            } else {
                document.getElementById('navType').value = 'custom';
                document.getElementById('navUrl').value = item.url || '';
                document.getElementById('navPageId').value = '';
                urlGroup.style.display = '';
                pageGroup.style.display = 'none';
            }

            modal.classList.add('show');
        });
    });

    // Submit form
    document.getElementById('navSubmit').addEventListener('click', async () => {
        const id = document.getElementById('navItemId').value;
        const isNew = !id;

        const data = {
            label: document.getElementById('navLabel').value,
            is_visible: document.getElementById('navVisible').checked,
            open_in_new_tab: document.getElementById('navNewTab').checked,
            parent_id: document.getElementById('navParentId').value || null
        };

        if (navType.value === 'page') {
            data.page_id = document.getElementById('navPageId').value || null;
            data.url = null;
        } else {
            data.url = document.getElementById('navUrl').value;
            data.page_id = null;
        }

        if (!data.label) {
            showToast('Label is required', 'error');
            return;
        }

        try {
            const url = isNew ? '/api/admin/navigation' : `/api/admin/navigation/${id}`;
            const method = isNew ? 'POST' : 'PUT';

            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                showToast(isNew ? 'Item added' : 'Item updated', 'success');
                location.reload();
            } else {
                const result = await response.json();
                showToast(result.error || 'Failed to save', 'error');
            }
        } catch (error) {
            showToast('Network error', 'error');
        }
    });

    // Delete item
    document.querySelectorAll('.delete-nav-item').forEach(btn => {
        btn.addEventListener('click', async function() {
            const id = this.dataset.id;
            const label = this.dataset.label;

            const confirmed = await showConfirm(
                'Delete Menu Item',
                `Are you sure you want to delete "${label}"?`
            );

            if (confirmed) {
                try {
                    const response = await fetch(`/api/admin/navigation/${id}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        showToast('Item deleted', 'success');
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

    // Drag and drop reordering
    if (navItemsList) {
        let draggedItem = null;

        navItemsList.querySelectorAll('.nav-item-row').forEach(item => {
            item.draggable = true;

            item.addEventListener('dragstart', function() {
                draggedItem = this;
                this.classList.add('dragging');
            });

            item.addEventListener('dragend', function() {
                this.classList.remove('dragging');
                saveOrder();
            });

            item.addEventListener('dragover', function(e) {
                e.preventDefault();
                const afterElement = getDragAfterElement(navItemsList, e.clientY);
                if (afterElement == null) {
                    navItemsList.appendChild(draggedItem);
                } else {
                    navItemsList.insertBefore(draggedItem, afterElement);
                }
            });
        });
    }

    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.nav-item-row:not(.dragging)')];

        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    async function saveOrder() {
        const items = [];
        navItemsList.querySelectorAll('.nav-item-row').forEach((item, index) => {
            items.push({
                id: item.dataset.id,
                position: index,
                parent_id: item.dataset.parent || null
            });
        });

        try {
            const response = await fetch('/api/admin/navigation/reorder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items })
            });

            if (response.ok) {
                showToast('Order saved', 'success');
            }
        } catch (error) {
            console.error('Failed to save order:', error);
        }
    }
});

function closeNavModal() {
    document.getElementById('navModal').classList.remove('show');
}
