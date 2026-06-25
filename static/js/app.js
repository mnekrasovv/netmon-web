// App entry — tab routing, dashboard, initial loads

const App = {
  async showTab(name) {
    $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    $$('.panel').forEach(p => p.classList.toggle('active', p.id === `panel-${name}`));
    if (name === 'dashboard') await Dashboard.refresh();
    if (name === 'reports') await Reports.refresh();
    if (name === 'hosts') { await Hosts.load(); Hosts.render(); }
    location.hash = name;
  },

  initTabs() {
    $$('.tab').forEach(t => {
      t.addEventListener('click', () => this.showTab(t.dataset.tab));
    });
    $$('[data-tab-go]').forEach(b => {
      b.addEventListener('click', () => this.showTab(b.dataset.tabGo));
    });
  },

  startClock() {
    const tick = () => {
      $('#sys-time').textContent = new Date().toLocaleString('ru-RU', { hour12: false });
    };
    tick();
    setInterval(tick, 1000);
  },
};

const Dashboard = {
  async refresh() {
    try {
      const sys = await API.get('/api/sysinfo');
      $('#sys-host').textContent = sys.hostname || '—';

      const t = $('#sysinfo-table');
      t.innerHTML = '';
      const rows = [
        ['Hostname', sys.hostname],
        ['ОС', sys.os + (sys.distrib ? ` · ${sys.distrib}` : '')],
        ['Архитектура', sys.arch],
        ['Python', sys.python],
        ['Uptime', sys.uptime],
        ['Пользователь', sys.user],
      ];
      rows.forEach(([k, v]) => {
        if (!v) return;
        const tr = el('tr', {}, el('td', {}, k), el('td', {}, String(v)));
        t.appendChild(tr);
      });

      const hosts = await API.get('/api/hosts');
      $('#card-hosts').textContent = hosts.hosts.length;

      const gw = await API.get('/api/gateway');
      $('#card-gw').textContent = gw.gateway || '—';

      // External IP — fire and forget (could be slow)
      this.loadExternalIP();
      await Reports.refresh();
    } catch (e) {
      console.error(e);
    }
  },

  async loadExternalIP() {
    try {
      const r = await API.get('/api/external-ip');
      const ip = r.geo?.ip || Object.values(r.services).find(x => x) || '—';
      $('#card-ip').textContent = ip;
    } catch (e) {
      $('#card-ip').textContent = '—';
    }
  },
};

document.addEventListener('DOMContentLoaded', async () => {
  App.initTabs();
  App.startClock();
  Hosts.initUI();
  Diagnose.initUI();
  Monitor.initUI();
  Reports.initUI();

  await Hosts.load();
  Hosts.render();
  Diagnose.renderHostsList();
  await Monitor.loadCategories();

  const tab = (location.hash || '#dashboard').slice(1);
  await App.showTab(['dashboard','diagnose','monitor','hosts','reports'].includes(tab) ? tab : 'dashboard');
});

// quick-action handler
document.addEventListener('click', (e) => {
  if (e.target.matches('[data-quick="dashboard-refresh"]')) Dashboard.refresh();
});
