// App entry: tab routing, clock, init

const App = {
  current: null,

  async showTab(name) {
    if (this.current === name) return;
    if (this.current === 'dashboard') Dashboard.deactivate();
    this.current = name;

    $$('.nav-item').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    $$('.panel').forEach(p => p.classList.toggle('active', p.id === `panel-${name}`));

    const titles = {
      dashboard: 'Dashboard',
      diagnose:  'Diagnose',
      monitor:   'Monitor',
      hosts:     'Hosts',
      sites:     'Sites editor',
      tools:     'Tools',
      reports:   'Reports',
    };
    $('#page-title').textContent = titles[name] || name;

    if (name === 'dashboard') await Dashboard.activate();
    if (name === 'reports')   await Reports.refresh();
    if (name === 'hosts')     { await Hosts.load(); Hosts.render(); }
    if (name === 'sites')     await Sites.load();
    if (name === 'monitor')   await Monitor.loadCategories();

    location.hash = name;
  },

  initNav() {
    $$('.nav-item').forEach(t => t.addEventListener('click', () => this.showTab(t.dataset.tab)));
  },

  startClock() {
    const tick = () => {
      $('#sys-time').textContent = new Date().toLocaleString('ru-RU', { hour12: false });
    };
    tick();
    setInterval(tick, 1000);
  },

  initModal() {
    $('#modal-close').addEventListener('click', closeModal);
    $('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });
  },
};

document.addEventListener('DOMContentLoaded', async () => {
  Theme.init();
  App.initNav();
  App.startClock();
  App.initModal();
  Hosts.initUI();
  Diagnose.initUI();
  Monitor.initUI();
  Tools.initUI();
  Sites.initUI();
  Reports.initUI();
  Dashboard.initUI();

  Version.load();
  await Tools.loadPresets();
  await Hosts.load();
  Hosts.render();
  Diagnose.renderHostsList();

  const tab = (location.hash || '#dashboard').slice(1);
  const valid = ['dashboard', 'diagnose', 'monitor', 'tools', 'hosts', 'sites', 'reports'];
  await App.showTab(valid.includes(tab) ? tab : 'dashboard');
});
