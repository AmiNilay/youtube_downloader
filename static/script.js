document.querySelector('.menu-toggle')?.addEventListener('click', () => {
    const navItems = document.querySelector('.nav-items');
    navItems.classList.toggle('active');
});

function toggleTheme() {
    const body = document.body;
    const themeBtn = document.getElementById('themeBtn');
    if (body.getAttribute('data-theme') === 'dark') {
        body.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
        if (themeBtn) themeBtn.textContent = 'Dark Mode';
    } else {
        body.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
        if (themeBtn) themeBtn.textContent = 'Light Mode';
    }
}

window.onload = () => {
    const savedTheme = localStorage.getItem('theme');
    const themeBtn = document.getElementById('themeBtn');
    if (savedTheme) {
        if (savedTheme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
            if (themeBtn) themeBtn.textContent = 'Light Mode';
        } else {
            document.body.removeAttribute('data-theme');
            if (themeBtn) themeBtn.textContent = 'Dark Mode';
        }
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.body.setAttribute('data-theme', 'dark');
        if (themeBtn) themeBtn.textContent = 'Light Mode';
    } else {
        document.body.removeAttribute('data-theme');
        if (themeBtn) themeBtn.textContent = 'Dark Mode';
    }
};