// INPUT PANEL FUNCTIONS (ADD THIS TO YOUR EXISTING SCRIPT)

function openInputPanel() {
    const panel = document.getElementById('inputPanel');
    panel.classList.add('open');
    document.body.style.overflow = 'hidden';
    document.getElementById('expenseCategory').focus();
}

function closeInputPanel() {
    const panel = document.getElementById('inputPanel');
    panel.classList.remove('open');
    document.body.style.overflow = 'auto';
    document.getElementById('inputForm').reset();
    // Reset date to today
    document.getElementById('expenseDate').valueAsDate = new Date();
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Set today's date by default
    document.getElementById('expenseDate').valueAsDate = new Date();

    // Form submission
    document.getElementById('inputForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const category = document.getElementById('expenseCategory').value;
        const amount = document.getElementById('expenseAmount').value;
        const date = document.getElementById('expenseDate').value;
        const description = document.getElementById('expenseDescription').value;
        
        try {
            const response = await fetch('/api/add_expense', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, amount, date, description })
            });
            
            if (response.ok) {
                alert('✓ Expense added!');
                closeInputPanel();
                // Reload dashboard if you have data refresh function
                if (typeof loadDashboardData === 'function') {
                    loadDashboardData();
                }
            } else {
                alert('❌ Error adding expense');
            }
        } catch (error) {
            alert('❌ Network error');
            console.error(error);
        }
    });
    
    // Close panel with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeInputPanel();
        }
    });
});