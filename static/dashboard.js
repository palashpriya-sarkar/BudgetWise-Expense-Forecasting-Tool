let isEditingBudget = false;
let expenseChart = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadDashboardData();
    setDefaultDates();
    setupEventListeners();
});

function setDefaultDates() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('expense-date').value = today;
    document.getElementById('income-date').value = today;
}

function setupEventListeners() {
    // Budget input enter key
    document.getElementById('budget-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') editBudget();
    });

    // Expense form submit
    document.getElementById('expenseForm').addEventListener('submit', handleExpenseSubmit);

    // Income form submit
    document.getElementById('incomeForm').addEventListener('submit', handleIncomeSubmit);

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            const dropdown = document.getElementById('dropdownMenu');
            if (dropdown) dropdown.classList.remove('show');
        }
    });

    // Close modals when clicking outside
    window.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            closeExpenseModal();
            closeIncomeModal();
        }
    });
}

// Dropdown Menu
function toggleDropdown() {
    const dropdown = document.getElementById('dropdownMenu');
    dropdown.classList.toggle('show');
}

// Budget Editing
async function editBudget() {
    const display = document.getElementById('budget-display');
    const input = document.getElementById('budget-input');
    
    if (!isEditingBudget) {
        isEditingBudget = true;
        input.value = display.textContent.replace(/[₹,]/g, '') || '';
        display.style.display = 'none';
        input.style.display = 'block';
        input.focus();
    } else {
        const amount = parseFloat(input.value);
        if (amount && amount > 0) {
            const month = new Date().toISOString().slice(0, 7);
            try {
                const response = await fetch('/api/update_budget', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({amount: amount, month_year: month})
                });
                if (response.ok) {
                    display.textContent = `₹${amount.toLocaleString()}`;
                    display.classList.remove('null-state');
                    input.style.display = 'none';
                    display.style.display = 'block';
                    showAlert('Budget updated successfully!', 'success');
                    loadDashboardData();
                }
            } catch (error) {
                showAlert('Failed to update budget', 'error');
            }
        }
        isEditingBudget = false;
    }
}

// Load Dashboard Data
async function loadDashboardData() {
    try {
        const response = await fetch('/api/get_dashboard_data');
        const data = await response.json();
        
        // Update metrics
        updateMetrics(data);
        
        // Load transactions
        loadTransactions();
        
        // Update chart
        updateExpenseChart(data.categories);
        
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

function updateMetrics(data) {
    // Total Expenses
    const expensesEl = document.getElementById('total-expenses');
    expensesEl.textContent = `₹${data.expenses.toLocaleString()}`;
    
    // Budget
    const budgetEl = document.getElementById('budget-display');
    if (data.budget > 0) {
        budgetEl.textContent = `₹${data.budget.toLocaleString()}`;
        budgetEl.classList.remove('null-state');
    }
    
    // Remaining Balance (Budget - Expenses + Income)
    const remainingEl = document.getElementById('remaining-balance');
    if (data.budget > 0) {
        const remaining = data.budget - data.expenses + data.income;
        remainingEl.textContent = `₹${remaining.toLocaleString()}`;
        remainingEl.classList.remove('null-state');
        
        // Color based on remaining balance
        if (remaining < 0) {
            remainingEl.style.color = '#ef4444';
        } else if (remaining < data.budget * 0.2) {
            remainingEl.style.color = '#f59e0b';
        } else {
            remainingEl.style.color = '#8b5cf6';
        }
    }
}

// Load Transactions
async function loadTransactions() {
    try {
        const response = await fetch('/api/get_transactions');
        const transactions = await response.json();
        
        const container = document.getElementById('transactions-list');
        
        if (transactions.length === 0) {
            container.innerHTML = '<p class="empty-state">No transactions yet</p>';
            return;
        }
        
        container.innerHTML = transactions.map(t => `
            <div class="transaction-item">
                <div class="transaction-info">
                    <span class="transaction-name">${t.name}</span>
                    <span class="transaction-date">${formatDate(t.date)}</span>
                </div>
                <span class="transaction-amount ${t.type}">
                    ${t.type === 'expense' ? '-' : '+'}₹${t.amount.toLocaleString()}
                </span>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading transactions:', error);
    }
}

// Update Expense Chart
function updateExpenseChart(categories) {
    const ctx = document.getElementById('expenseChart').getContext('2d');
    
    if (Object.keys(categories).length === 0) {
        if (expenseChart) {
            expenseChart.destroy();
            expenseChart = null;
        }
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.font = '16px Segoe UI';
        ctx.fillStyle = '#9ca3af';
        ctx.textAlign = 'center';
        ctx.fillText('No expenses yet', ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }
    
    const labels = Object.keys(categories);
    const data = Object.values(categories);
    const colors = [
        '#a300d4', '#10b981', '#073174', '#00e8f8', 
        '#871313', '#ec4899', '#f6ff00', '#676867'
    ];
    
    if (expenseChart) {
        expenseChart.data.labels = labels;
        expenseChart.data.datasets[0].data = data;
        expenseChart.update();
    } else {
        expenseChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ₹${value.toLocaleString()} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
}

// Expense Modal
function openExpenseModal() {
    document.getElementById('expenseModal').classList.add('show');
}

function closeExpenseModal() {
    document.getElementById('expenseModal').classList.remove('show');
    document.getElementById('expenseForm').reset();
    setDefaultDates();
}

async function handleExpenseSubmit(e) {
    e.preventDefault();
    
    const category = document.getElementById('expense-category').value;
    const amount = parseFloat(document.getElementById('expense-amount').value);
    const date = document.getElementById('expense-date').value;
    const description = document.getElementById('expense-description').value;
    
    try {
        const response = await fetch('/api/add_expense', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ category, amount, date, description })
        });
        
        if (response.ok) {
            showAlert('Expense added successfully!', 'success');
            closeExpenseModal();
            loadDashboardData();
        } else {
            showAlert('Failed to add expense', 'error');
        }
    } catch (error) {
        showAlert('Network error. Please try again.', 'error');
        console.error('Error:', error);
    }
}

// Income Modal
function openIncomeModal() {
    document.getElementById('incomeModal').classList.add('show');
}

function closeIncomeModal() {
    document.getElementById('incomeModal').classList.remove('show');
    document.getElementById('incomeForm').reset();
    setDefaultDates();
}

async function handleIncomeSubmit(e) {
    e.preventDefault();
    
    const source = document.getElementById('income-source').value;
    const amount = parseFloat(document.getElementById('income-amount').value);
    const date = document.getElementById('income-date').value;
    const description = document.getElementById('income-description').value;
    
    try {
        const response = await fetch('/api/add_income', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ source, amount, date, description })
        });
        
        if (response.ok) {
            showAlert('Income added successfully!', 'success');
            closeIncomeModal();
            loadDashboardData();
        } else {
            showAlert('Failed to add income', 'error');
        }
    } catch (error) {
        showAlert('Network error. Please try again.', 'error');
        console.error('Error:', error);
    }
}

// Alert System
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

// Utility Functions
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}
