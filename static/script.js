document.addEventListener('DOMContentLoaded', function() {
    // ========== INPUT PANEL FUNCTIONS ==========
    function openInputPanel() {
        document.getElementById('inputPanel').classList.add('open');
        document.body.style.overflow = 'hidden';
        document.getElementById('expenseCategory').focus();
    }

    function closeInputPanel() {
        document.getElementById('inputPanel').classList.remove('open');
        document.body.style.overflow = 'auto';
        document.getElementById('inputForm').reset();
        document.getElementById('expenseDate').valueAsDate = new Date();
    }

    // Set today's date
    if (document.getElementById('expenseDate')) {
        document.getElementById('expenseDate').valueAsDate = new Date();
    }

    // Form submission
    const inputForm = document.getElementById('inputForm');
    if (inputForm) {
        inputForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const category = document.getElementById('expenseCategory').value;
            const amount = parseFloat(document.getElementById('expenseAmount').value);
            const date = document.getElementById('expenseDate').value;
            const description = document.getElementById('expenseDescription').value;
            
            try {
                const response = await fetch('/api/add_expense', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ category, amount, date, description })
                });
                
                const result = await response.json();
                if (response.ok && result.success) {
                    alert('✓ Expense added successfully!');
                    closeInputPanel();
                    location.reload(); // Refresh dashboard
                } else {
                    alert('❌ Failed to add expense');
                }
            } catch (error) {
                alert('❌ Network error: ' + error.message);
            }
        });
    }

    // Close with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeInputPanel();
        }
    });

    // Mobile toggle button
    if (window.innerWidth <= 768) {
        document.getElementById('inputToggleBtn').classList.add('show');
    }

    // ========== EXISTING DASHBOARD FUNCTIONS ==========
    let isEditingBudget = false;

    async function editBudget() {
        const display = document.getElementById('budget-display');
        const input = document.getElementById('budget-input');
        
        if (!isEditingBudget) {
            isEditingBudget = true;
            input.value = display.textContent.replace(/,/g, '');
            display.style.display = 'none';
            input.style.display = 'block';
            input.focus();
        } else {
            const amount = parseFloat(input.value);
            if (amount || amount === 0) {
                const month = new Date().toISOString().slice(0, 7);
                try {
                    const response = await fetch('/api/update_budget', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ amount, month_year: month })
                    });
                    if (response.ok) {
                        display.textContent = amount.toLocaleString();
                        display.classList.remove('null-state');
                        input.style.display = 'none';
                        display.style.display = 'block';
                        showAlert('Budget updated successfully!', 'success');
                    }
                } catch (error) {
                    showAlert('Failed to update budget', 'error');
                }
                isEditingBudget = false;
            }
        }
    }

    function openProfile() {
        alert('Profile page coming soon!');
    }

    function showAlert(message, type = 'info') {
        const alertEl = document.getElementById('alert');
        const messageEl = document.getElementById('alert-message');
        messageEl.textContent = message;
        alertEl.className = `alert ${type}`;
        alertEl.style.display = 'block';
        alertEl.classList.add('show');
        setTimeout(() => {
            alertEl.classList.remove('show');
            setTimeout(() => alertEl.style.display = 'none', 400);
        }, 3000);
    }

    // Handle Enter key in budget input
    document.getElementById('budget-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            editBudget();
        }
    });

    // Expose functions globally
    window.openInputPanel = openInputPanel;
    window.closeInputPanel = closeInputPanel;
    window.editBudget = editBudget;
});
