/**
 * CRC Portal — Client-Side JavaScript
 * Vanilla JS only (no frameworks).
 */

document.addEventListener('DOMContentLoaded', () => {
    initFlashMessages();
    initSlotPicker();
    initDayFilterAjax();
    initSelectAllSlots();
    initFormValidation();
});


// ── Flash message auto-dismiss ──
function initFlashMessages() {
    const flashes = document.querySelectorAll('.flash-msg');
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.animation = 'flashSlideIn 0.3s ease-out reverse forwards';
            setTimeout(() => flash.remove(), 300);
        }, 5000);

        // Click to dismiss
        flash.addEventListener('click', () => {
            flash.style.animation = 'flashSlideIn 0.3s ease-out reverse forwards';
            setTimeout(() => flash.remove(), 300);
        });
    });
}


// ── Slot picker: highlight selected count ──
function initSlotPicker() {
    const picker = document.getElementById('slot-picker');
    if (!picker) return;

    const countDisplay = document.getElementById('slot-count');
    const checkboxes = picker.querySelectorAll('input[type="checkbox"]');

    function updateCount() {
        const checked = picker.querySelectorAll('input:checked').length;
        if (countDisplay) {
            countDisplay.textContent = `${checked} slot${checked !== 1 ? 's' : ''} selected`;
        }
    }

    checkboxes.forEach(cb => cb.addEventListener('change', updateCount));
    updateCount();
}


// ── Day filter: AJAX to reload available slots ──
function initDayFilterAjax() {
    const daySelect = document.getElementById('day-filter');
    if (!daySelect) return;

    daySelect.addEventListener('change', async () => {
        const dayFilter = daySelect.value;
        const picker = document.getElementById('slot-picker');
        const loader = document.getElementById('slot-loader');

        if (loader) loader.style.display = 'flex';
        if (picker) picker.innerHTML = '';

        try {
            const response = await fetch(`/allocator/api/slots?day_filter=${encodeURIComponent(dayFilter)}`);
            const data = await response.json();

            if (data.error) {
                if (picker) picker.innerHTML = `<p class="empty-state">${data.error}</p>`;
                return;
            }

            const slots = data.slots || [];
            if (slots.length === 0) {
                if (picker) picker.innerHTML = '<p class="empty-state">No free slots found for this day.</p>';
                return;
            }

            let html = '';
            slots.forEach((slot, i) => {
                html += `
          <div class="slot-option">
            <input type="checkbox" name="selected_slots" value="${slot}" id="slot-${i}">
            <label for="slot-${i}">🕐 ${slot}</label>
          </div>
        `;
            });

            if (picker) {
                picker.innerHTML = html;
                initSlotPicker(); // Re-bind
            }
        } catch (err) {
            if (picker) picker.innerHTML = '<p class="empty-state">Error loading slots. Please try again.</p>';
        } finally {
            if (loader) loader.style.display = 'none';
        }
    });

    // Trigger initial load so the slots are fetched asynchronously on page load
    daySelect.dispatchEvent(new Event('change'));
}


// ── Select All / Deselect All slots ──
function initSelectAllSlots() {
    const selectAllBtn = document.getElementById('select-all-slots');
    const deselectAllBtn = document.getElementById('deselect-all-slots');
    const picker = document.getElementById('slot-picker');

    if (selectAllBtn && picker) {
        selectAllBtn.addEventListener('click', () => {
            picker.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
            initSlotPicker();
        });
    }

    if (deselectAllBtn && picker) {
        deselectAllBtn.addEventListener('click', () => {
            picker.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            initSlotPicker();
        });
    }
}


// ── Basic form validation ──
function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const required = form.querySelectorAll('[required]');
            let valid = true;

            required.forEach(field => {
                if (!field.value.trim()) {
                    valid = false;
                    field.style.borderColor = 'var(--accent-red)';
                    field.addEventListener('input', () => {
                        field.style.borderColor = '';
                    }, { once: true });
                }
            });

            if (!valid) {
                e.preventDefault();
                showToast('Please fill in all required fields.', 'danger');
            }
        });
    });
}


// ── Simple toast notification ──
function showToast(message, type = 'info') {
    const container = document.querySelector('.flash-container') || createFlashContainer();
    const flash = document.createElement('div');
    flash.className = `flash-msg flash-${type}`;
    flash.textContent = message;
    container.appendChild(flash);

    setTimeout(() => {
        flash.style.animation = 'flashSlideIn 0.3s ease-out reverse forwards';
        setTimeout(() => flash.remove(), 300);
    }, 4000);
}


function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-container';
    document.body.appendChild(container);
    return container;
}
