document.addEventListener('DOMContentLoaded', function() {
    // ELEMENT REFERENCES
    const switchContainer = document.getElementById('switch-cnt');
    const switchContent1 = document.getElementById('switch-c1');
    const switchContent2 = document.getElementById('switch-c2');
    const switchCircles = document.querySelectorAll('.switchcircle');
    const switchButtons = document.querySelectorAll('.switch-btn');
    const signupContainer = document.getElementById('a-container');
    const loginContainer = document.getElementById('b-container');
    const signupForm = document.getElementById('a-form');
    const loginForm = document.getElementById('b-form');

    // FORM SWITCH HANDLER (SLIDING EFFECT)
    const toggleForms = function() {
        if (!switchContainer) return;
        
        switchContainer.classList.add('is-gx');
        setTimeout(() => {
            switchContainer.classList.remove('is-gx');
        }, 1500);
        
        switchContainer.classList.toggle('is-txr');
        switchCircles.forEach(circle => {
            circle.classList.toggle('is-txr');
        });
        switchContent1.classList.toggle('is-hidden');
        switchContent2.classList.toggle('is-hidden');
        signupContainer.classList.toggle('is-txl');
        loginContainer.classList.toggle('is-txl');
        loginContainer.classList.toggle('is-z200');
    };

    // SWITCH BUTTON EVENTS
    switchButtons.forEach(button => {
        button.addEventListener('click', toggleForms);
    });

    // SIGNUP SUBMIT - WORKS WITH FLASK
    if (signupForm) {
        signupForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const nameInput = signupForm.querySelector('input[placeholder="Name"]');
            const emailInput = signupForm.querySelector('input[placeholder="Email"]');
            const passwordInput = signupForm.querySelector('input[placeholder="Password"]');
            
            const name = nameInput.value.trim();
            const email = emailInput.value.trim();
            const password = passwordInput.value;
            
            try {
                const formData = new FormData();
                formData.append('name', name);
                formData.append('email', email);
                formData.append('password', password);
                
                const response = await fetch('/signup', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert('Signup successful! Redirecting...');
                    window.location.href = '/dashboard';
                } else {
                    alert(result.message || 'Signup failed');
                    // Clear password field on error
                    passwordInput.value = '';
                }
            } catch (error) {
                alert('Network error. Please try again.');
                console.error('Signup error:', error);
            }
        });
    }

    // LOGIN SUBMIT - WORKS WITH FLASK
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const emailInput = loginForm.querySelector('input[placeholder="Email"]');
            const passwordInput = loginForm.querySelector('input[placeholder="Password"]');
            
            const email = emailInput.value.trim();
            const password = passwordInput.value;
            
            try {
                const formData = new FormData();
                formData.append('email', email);
                formData.append('password', password);
                
                const response = await fetch('/login', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    window.location.href = '/dashboard';
                } else {
                    alert(result.message || 'Login failed');
                    // Clear password field on error
                    passwordInput.value = '';
                }
            } catch (error) {
                alert('Network error. Please try again.');
                console.error('Login error:', error);
            }
        });
    }

    // INPUT FOCUS EFFECTS
    const inputs = document.querySelectorAll('.forminput');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentNode.classList.add('focus');
        });
        input.addEventListener('blur', function() {
            if (this.value === '') {
                this.parentNode.classList.remove('focus');
            }
        });
    });

    // KEYBOARD SUPPORT
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Escape toggles back to login
            if (!signupContainer.classList.contains('is-txl')) {
                toggleForms();
            }
        }
    });
});
