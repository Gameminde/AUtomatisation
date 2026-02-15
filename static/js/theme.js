/**
 * Content Factory v2.0 - Theme Manager
 * Handles Light/Dark mode toggling and persistence.
 */

class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('ui_theme') || 'dark';
        this.init();
    }

    init() {
        this.applyTheme(this.currentTheme);
        this.updateUI();
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('ui_theme', this.currentTheme);
        this.applyTheme(this.currentTheme);
        this.updateUI();
    }

    applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-theme');
        } else {
            document.body.classList.remove('light-theme');
        }
    }

    updateUI() {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            const isDark = this.currentTheme === 'dark';
            btn.innerHTML = isDark ? '<i class="fa-solid fa-moon"></i>' : '<i class="fa-solid fa-sun text-warning"></i>';
            btn.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
        }
    }
}

// Initialize
window.themeManager = new ThemeManager();

// Expose global toggle function for button onClick
window.toggleTheme = () => window.themeManager.toggleTheme();
