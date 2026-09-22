/* ============================================
   LEGALEASE - MAIN JAVASCRIPT
   ============================================ */

document.addEventListener('DOMContentLoaded', function () {

    // ========== MOBILE NAV TOGGLE ==========
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function () {
            navMenu.classList.toggle('active');
            const icon = navToggle.querySelector('i');
            if (navMenu.classList.contains('active')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-times');
            } else {
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });

        // Close menu when clicking outside
        document.addEventListener('click', function (e) {
            if (!navToggle.contains(e.target) && !navMenu.contains(e.target)) {
                navMenu.classList.remove('active');
                const icon = navToggle.querySelector('i');
                icon.classList.remove('fa-times');
                icon.classList.add('fa-bars');
            }
        });
    }

    // ========== FLASH MESSAGE AUTO-DISMISS ==========
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function (msg) {
        setTimeout(function () {
            msg.style.transition = 'all 0.5s ease';
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(function () { msg.remove(); }, 500);
        }, 5000);
    });

    // ========== DASHBOARD FILTER TABS ==========
    const filterBtns = document.querySelectorAll('.filter-btn');
    const caseItems = document.querySelectorAll('.case-item');

    filterBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            // Update active tab
            filterBtns.forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');

            const filter = btn.getAttribute('data-filter');

            caseItems.forEach(function (item) {
                const status = item.getAttribute('data-status');
                if (filter === 'all' || status === filter) {
                    item.style.display = 'flex';
                    item.style.animation = 'messageIn 0.3s ease';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    });

    // ========== PASSWORD TOGGLE ==========
    window.togglePassword = function (fieldId) {
        const field = document.getElementById(fieldId);
        const btn = field.nextElementSibling || field.parentElement.querySelector('.toggle-password');
        if (field.type === 'password') {
            field.type = 'text';
            if (btn) btn.innerHTML = '<i class="fas fa-eye-slash"></i>';
        } else {
            field.type = 'password';
            if (btn) btn.innerHTML = '<i class="fas fa-eye"></i>';
        }
    };

    // ========== COMPLETE REMINDER (GLOBAL) ==========
    window.completeReminder = function (reminderId) {
        fetch('/reminder/' + reminderId + '/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.status === 'success') {
                const reminderEl = document.getElementById('reminder-' + reminderId);
                if (reminderEl) {
                    reminderEl.classList.add('completed');
                    const checkBtn = reminderEl.querySelector('.check-btn');
                    if (checkBtn) {
                        checkBtn.outerHTML = '<span class="check-done"><i class="fas fa-check-circle"></i></span>';
                    }
                    // Add strike-through to title
                    const title = reminderEl.querySelector('h4') || reminderEl.querySelector('strong');
                    if (title) {
                        title.style.textDecoration = 'line-through';
                    }
                    // Update status badge if present
                    const statusBadge = reminderEl.querySelector('.reminder-status');
                    if (statusBadge) {
                        statusBadge.innerHTML = '<span class="badge-completed">✅ Done</span>';
                    }
                }
            }
        })
        .catch(function (error) {
            console.error('Error completing reminder:', error);
            alert('Failed to complete reminder. Please try again.');
        });
    };

    // ========== SMOOTH SCROLL FOR ANCHOR LINKS ==========
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ========== FORM VALIDATION ENHANCEMENTS ==========
    const forms = document.querySelectorAll('form');
    forms.forEach(function (form) {
        const inputs = form.querySelectorAll('.form-input[required]');
        inputs.forEach(function (input) {
            input.addEventListener('invalid', function () {
                this.style.borderColor = '#ef4444';
                this.style.boxShadow = '0 0 0 3px rgba(239,68,68,0.1)';
            });
            input.addEventListener('input', function () {
                if (this.validity.valid) {
                    this.style.borderColor = '';
                    this.style.boxShadow = '';
                }
            });
        });
    });

    // ========== ADD ANIMATION ON SCROLL (for feature cards) ==========
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .step, .stat-card').forEach(function (el) {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'all 0.6s ease';
        observer.observe(el);
    });

    // ========== NAVBAR SCROLL EFFECT ==========
    let lastScroll = 0;
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', function () {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > 50) {
            navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.1)';
        } else {
            navbar.style.boxShadow = 'var(--shadow-sm)';
        }
        
        lastScroll = currentScroll;
    });

    // ========== TEXTAREA AUTO-RESIZE ==========
    document.querySelectorAll('textarea.form-input').forEach(function (textarea) {
        textarea.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    // ========== PRINT FUNCTION (for case detail) ==========
    window.printCase = function () {
        window.print();
    };

    console.log('🏛️ LegalEase initialized successfully');
});