/**
 * CRC Portal — Client-Side JavaScript
 * Vanilla JS only (no frameworks).
 */

document.addEventListener('DOMContentLoaded', () => {
    initFlashMessages();
    initSlotPicker();
    initDayFilterAjax();
    initSelectAllSlots();
    initCustomSlot();
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


// ── Custom Slot: add user-defined time slots ──
function initCustomSlot() {
    const addBtn = document.getElementById('add-custom-slot');
    const input = document.getElementById('custom-slot-input');
    if (!addBtn || !input) return;

    /**
     * Parse "10:35 AM" → minutes since midnight, or null if invalid.
     */
    function parseTime(s) {
        const m = s.trim().toUpperCase().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/);
        if (!m) return null;
        let hours = parseInt(m[1], 10);
        const minutes = parseInt(m[2], 10);
        const period = m[3];
        if (hours < 1 || hours > 12 || minutes < 0 || minutes > 59) return null;
        if (period === 'AM' && hours === 12) hours = 0;
        else if (period === 'PM' && hours !== 12) hours += 12;
        return hours * 60 + minutes;
    }

    /**
     * Normalize "9:00 am" → "9:00 AM", "09:00am" → "9:00 AM"
     */
    function normalizeTimePart(s) {
        const m = s.trim().toUpperCase().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/);
        if (!m) return null;
        return `${parseInt(m[1], 10)}:${m[2]} ${m[3]}`;
    }

    function addCustomSlot() {
        let raw = input.value.trim();

        if (!raw) {
            showToast('Please enter a time slot.', 'warning');
            input.focus();
            return;
        }

        // Must contain "-"
        if (!raw.includes('-')) {
            showToast('Please follow the format: HH:MM AM - HH:MM PM', 'danger');
            input.focus();
            return;
        }

        const parts = raw.split('-');
        if (parts.length !== 2) {
            showToast('Please follow the format: HH:MM AM - HH:MM PM', 'danger');
            input.focus();
            return;
        }

        // Normalize each side
        const startNorm = normalizeTimePart(parts[0]);
        const endNorm = normalizeTimePart(parts[1]);

        if (!startNorm || !endNorm) {
            showToast('Invalid time format. Use: HH:MM AM - HH:MM PM (e.g. 9:00 AM - 10:00 AM)', 'danger');
            input.focus();
            return;
        }

        // Check start < end
        const startMin = parseTime(parts[0]);
        const endMin = parseTime(parts[1]);
        if (startMin >= endMin) {
            showToast('Start time must be before end time.', 'danger');
            input.focus();
            return;
        }

        const normalized = `${startNorm} - ${endNorm}`;

        // Check for duplicates
        const picker = document.getElementById('slot-picker');
        if (picker) {
            const existing = picker.querySelectorAll('input[name="selected_slots"]');
            for (const cb of existing) {
                if (cb.value.trim().toLowerCase() === normalized.toLowerCase()) {
                    showToast('This slot already exists.', 'warning');
                    input.value = '';
                    input.focus();
                    return;
                }
            }

            // Remove empty state message if present
            const emptyMsg = picker.querySelector('.empty-state');
            if (emptyMsg) emptyMsg.remove();
        }

        // Generate unique ID and create custom slot chip with delete button
        const uid = 'custom-' + Date.now();
        const div = document.createElement('div');
        div.className = 'slot-option custom-slot-option';
        div.innerHTML = `
            <input type="checkbox" name="selected_slots" value="${normalized}" id="${uid}" checked>
            <label for="${uid}">✏️ ${normalized}</label>
            <button type="button" class="custom-slot-delete" title="Remove this slot">&times;</button>
        `;

        // Attach delete handler
        div.querySelector('.custom-slot-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            div.remove();
            initSlotPicker(); // update count
            showToast('Custom slot removed.', 'info');
        });

        if (picker) picker.appendChild(div);

        input.value = '';
        input.focus();
        initSlotPicker();
        showToast(`Custom slot "${normalized}" added!`, 'success');
    }

    addBtn.addEventListener('click', addCustomSlot);

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addCustomSlot();
        }
    });
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
