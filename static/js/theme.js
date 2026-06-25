// Theme toggle (checkbox switch) with localStorage persistence

const Theme = {
  current: 'dark',
  apply(name) {
    this.current = name;
    document.documentElement.setAttribute('data-theme', name);
    try { localStorage.setItem('netmon-theme', name); } catch {}
    const cb = document.getElementById('theme-toggle');
    if (cb) cb.checked = name === 'light';
  },
  toggle() { this.apply(this.current === 'dark' ? 'light' : 'dark'); },
  init() {
    let saved = 'dark';
    try { saved = localStorage.getItem('netmon-theme') || 'dark'; } catch {}
    this.apply(saved);
    const cb = document.getElementById('theme-toggle');
    if (cb) cb.addEventListener('change', () => this.apply(cb.checked ? 'light' : 'dark'));
  },
};
