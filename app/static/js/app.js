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


// ── Custom Slot: add user-defined time slots with strict validation ──
function initCustomSlot() {
    const addBtn = document.getElementById('add-custom-slot');
    const input = document.getElementById('custom-slot-input');
    if (!addBtn || !input) return;

    // Create inline error display element below the input
    const inputContainer = input.parentElement;
    let errorDiv = document.getElementById('custom-slot-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'custom-slot-error';
        errorDiv.style.cssText =
            'color: #ff6b6b; font-size: 0.82rem; margin-top: 0.4rem; ' +
            'min-height: 1.2em; transition: opacity 0.25s ease;';
        inputContainer.parentElement.appendChild(errorDiv);
    }

    /**
     * Show inline error below the input with shake animation.
     */
    function showSlotError(msg) {
        errorDiv.textContent = msg;
        errorDiv.style.opacity = '1';

        // Red border + shake
        input.style.borderColor = 'var(--accent-red, #ff6b6b)';
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 500);

        // Also show as toast for visibility
        showToast(msg, 'danger');
    }

    /**
     * Clear inline error state.
     */
    function clearSlotError() {
        errorDiv.textContent = '';
        errorDiv.style.opacity = '0';
        input.style.borderColor = '';
    }

    // Clear error on new input
    input.addEventListener('input', clearSlotError);

    /**
     * Validate a time slot string with granular error messages.
     * Returns { valid, error, startMin, endMin, normalized } object.
     */
    function validateTimeSlot(raw) {
        // ── Step 1: Overall format ──
        const pattern = /^(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)$/i;
        const m = raw.match(pattern);
        if (!m) {
            return { valid: false, error: "Invalid time format. Please use 'HH:MM AM/PM - HH:MM AM/PM'" };
        }

        const startH = parseInt(m[1], 10);
        const startMStr = m[2];
        const startPeriod = m[3].toUpperCase();
        const endH = parseInt(m[4], 10);
        const endMStr = m[5];
        const endPeriod = m[6].toUpperCase();
        const startM = parseInt(startMStr, 10);
        const endM = parseInt(endMStr, 10);

        // ── Step 2: Hour validation (1–12) ──
        if (startH < 1 || startH > 12 || endH < 1 || endH > 12) {
            return { valid: false, error: "Invalid hour. Use values between 1 and 12" };
        }

        // ── Step 3: Minute validation (00–59) ──
        if (startM < 0 || startM > 59 || endM < 0 || endM > 59) {
            return { valid: false, error: "Minutes must be between 00 and 59" };
        }

        // Convert to minutes since midnight
        let startTotal = startH;
        if (startPeriod === 'AM' && startTotal === 12) startTotal = 0;
        else if (startPeriod === 'PM' && startTotal !== 12) startTotal += 12;
        startTotal = startTotal * 60 + startM;

        let endTotal = endH;
        if (endPeriod === 'AM' && endTotal === 12) endTotal = 0;
        else if (endPeriod === 'PM' && endTotal !== 12) endTotal += 12;
        endTotal = endTotal * 60 + endM;

        // ── Step 4: Same start and end ──
        if (startTotal === endTotal) {
            return { valid: false, error: "Start and end time cannot be the same" };
        }

        // ── Step 5: End must be after start ──
        if (endTotal <= startTotal) {
            return { valid: false, error: "End time must be later than start time" };
        }

        // ── Step 6: Duration cap (max 2 hours = 120 minutes) ──
        if (endTotal - startTotal > 120) {
            return { valid: false, error: "Slot duration must not exceed 2 hours" };
        }

        // ── Normalize ──
        const normalized = `${startH}:${startMStr} ${startPeriod} - ${endH}:${endMStr} ${endPeriod}`;

        return { valid: true, error: '', startMin: startTotal, endMin: endTotal, normalized };
    }

    function addCustomSlot() {
        const raw = input.value.trim();

        if (!raw) {
            showSlotError('Please enter a time slot.');
            input.focus();
            return;
        }

        // ── Validate ──
        const result = validateTimeSlot(raw);
        if (!result.valid) {
            showSlotError(result.error);
            input.focus();
            return;
        }

        const normalized = result.normalized;
        clearSlotError();

        // ── Check for duplicates ──
        const picker = document.getElementById('slot-picker');
        if (picker) {
            const existing = picker.querySelectorAll('input[name="selected_slots"]');
            for (const cb of existing) {
                if (cb.value.trim().toLowerCase() === normalized.toLowerCase()) {
                    showSlotError('This slot already exists.');
                    input.value = '';
                    input.focus();
                    return;
                }
            }

            // Remove empty state message if present
            const emptyMsg = picker.querySelector('.empty-state');
            if (emptyMsg) emptyMsg.remove();
        }

        // ── Create custom slot chip with delete button ──
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
