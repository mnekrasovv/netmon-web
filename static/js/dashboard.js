// Dashboard: stats cards + live availability grid

const Dashboard = {
  services: [],
  history: {},      // {host: [latencies]}
  autoTimer: null,

  async refreshSys() {
    const sys = await API.get('/api/sysinfo');
    $('#dash-host').textContent = sys.hostname || '—';
    $('#dash-uptime').textContent = sys.uptime ? sys.uptime.split('.')[0] : '—';
    $('#sys-meta').textContent = `${sys.os || ''}`;

    const t = $('#sysinfo-table');
    t.innerHTML = '';
    [
      ['Hostname', sys.hostname],
      ['ОС', sys.os],
      ['Дистрибутив', sys.distrib],
      ['Архитектура', sys.arch],
      ['Python', sys.python],
      ['Uptime', sys.uptime],
      ['Пользователь', sys.user],
    ].forEach(([k, v]) => {
      if (!v) return;
      const tr = el('tr', {}, el('td', {}, k), el('td', {}, String(v)));
      t.appendChild(tr);
    });

    try {
      const gw = await API.get('/api/gateway');
      $('#dash-gw').textContent = gw.gateway || '—';
    } catch { $('#dash-gw').textContent = '—'; }

    // External IP (async, may be slow)
    API.get('/api/external-ip').then(r => {
      const ip = (r.geo && r.geo.ip) || Object.values(r.services || {}).find(x => x) || '—';
      $('#dash-ip').textContent = ip;
    }).catch(() => { $('#dash-ip').textContent = '—'; });
  },

  renderTile(svc) {
    const cls = (svc.status || 'OK').toLowerCase();
    const canvas = el('canvas');
    const tile = el('div', { class: `live-tile ${cls}`, onclick: () => this.detailsModal(svc) },
      el('div', { class: 'live-tile-top' },
        el('div', {},
          el('div', { class: 'live-tile-name' }, svc.name),
          el('div', { class: 'live-tile-host muted' }, svc.host),
        ),
        el('span', { class: `dot ${cls}` }),
      ),
      el('div', { class: 'live-tile-metrics' },
        el('div', {},
          el('div', { class: 'm-k' }, 'ping'),
          el('div', { class: 'm-v' }, svc.ping_avg != null ? `${svc.ping_avg.toFixed(0)}ms` : '—'),
        ),
        el('div', {},
          el('div', { class: 'm-k' }, `tcp:${svc.port}`),
          el('div', { class: 'm-v' }, svc.tcp_open ? `${svc.tcp_ms || '-'}ms` : 'closed'),
        ),
        el('div', {},
          el('div', { class: 'm-k' }, 'loss'),
          el('div', { class: 'm-v' }, `${(svc.ping_loss || 0).toFixed(0)}%`),
        ),
      ),
      el('div', { class: 'live-tile-spark' }, canvas),
    );
    setTimeout(() => {
      canvas.parentNode && drawSpark(canvas, this.history[svc.host] || []);
    }, 10);
    return tile;
  },

  detailsModal(svc) {
    const history = this.history[svc.host] || [];
    const body = el('div', {},
      el('div', { class: 'host-card-grid', style: 'margin-bottom: 12px' },
        kv('Host', svc.host),
        kv('Port', svc.port),
        kv('Status', svc.status),
        kv('Ping avg', svc.ping_avg != null ? `${svc.ping_avg}ms` : '—'),
        kv('TCP', svc.tcp_open ? `open · ${svc.tcp_ms}ms` : 'closed'),
        kv('Loss', `${svc.ping_loss || 0}%`),
      ),
      el('div', { class: 'muted xs', style: 'margin-bottom: 6px' }, `Последние ${history.length} замера`),
    );
    const canvas = el('canvas');
    const wrap = el('div', { style: 'height: 140px' }, canvas);
    body.appendChild(wrap);
    openModal(`${svc.name} (${svc.host})`, body);
    setTimeout(() => drawSpark(canvas, history), 50);
  },

  async refresh() {
    try {
      const r = await API.get('/api/live/check');
      this.services = r.results;
      // update history (rolling 60)
      this.services.forEach(s => {
        if (!this.history[s.host]) this.history[s.host] = [];
        this.history[s.host].push(s.ping_avg != null ? s.ping_avg : 0);
        if (this.history[s.host].length > 60) this.history[s.host].shift();
      });
      this.render();
    } catch (e) {
      console.error(e);
    }
  },

  render() {
    const grid = $('#live-grid');
    grid.innerHTML = '';
    this.services.forEach(s => grid.appendChild(this.renderTile(s)));
  },

  startAutoRefresh() {
    if (this.autoTimer) clearInterval(this.autoTimer);
    if (!$('#live-autorefresh').checked) return;
    const sec = Math.max(5, parseInt($('#live-interval').value || '15', 10));
    this.autoTimer = setInterval(() => this.refresh(), sec * 1000);
  },

  initUI() {
    $('#live-refresh').addEventListener('click', () => this.refresh());
    $('#live-autorefresh').addEventListener('change', () => this.startAutoRefresh());
    $('#live-interval').addEventListener('change', () => this.startAutoRefresh());
  },

  async activate() {
    await this.refreshSys();
    await this.refresh();
    this.startAutoRefresh();
  },

  deactivate() {
    if (this.autoTimer) { clearInterval(this.autoTimer); this.autoTimer = null; }
  },
};
