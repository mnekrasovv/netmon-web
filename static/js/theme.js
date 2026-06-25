// Theme toggle with localStorage persistence

const Theme = {
  current: 'dark',
  apply(name) {
    this.current = name;
    document.documentElement.setAttribute('data-theme', name);
    try { localStorage.setItem('netmon-theme', name); } catch {}
  },
  toggle() { this.apply(this.current === 'dark' ? 'light' : 'dark'); },
  init() {
    let saved = 'dark';
    try { saved = localStorage.getItem('netmon-theme') || 'dark'; } catch {}
    this.apply(saved);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', () => this.toggle());
  },
};
