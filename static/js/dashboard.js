// Dashboard: stats cards + live availability grid

const Dashboard = {
  services: [],
  history: {},      // {host: [latencies]}
  autoTimer: null,

  async refreshSys() {
    // Каждый блок изолирован — падение одного эндпоинта не должно ронять остальные
    try {
      const sys = await API.get('/api/sysinfo');
      const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
      set('#dash-host', sys.hostname || '—');
      set('#dash-uptime', sys.uptime ? sys.uptime.split('.')[0] : '—');

      const t = $('#sysinfo-table');
      if (t) {
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
          t.appendChild(el('tr', {}, el('td', {}, k), el('td', {}, String(v))));
        });
      }
    } catch (e) { console.error('sysinfo:', e); }

    try {
      const gw = await API.get('/api/gateway');
      const e = $('#dash-gw'); if (e) e.textContent = gw.gateway || '—';
    } catch (e) { console.error('gateway:', e); }

    // External IP — fire-and-forget, может быть медленным
    API.get('/api/external-ip').then(r => {
      const ip = (r.geo && r.geo.ip) || Object.values(r.services || {}).find(x => x) || '—';
      const e = $('#dash-ip'); if (e) e.textContent = ip;
    }).catch(() => {
      const e = $('#dash-ip'); if (e) e.textContent = '—';
    });
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

  async openEditor() {
    const data = await API.get('/api/live/services');
    const list = data.services.map(s => `${s.host} ${s.port} ${s.name}`).join('\n');
    const ta = el('textarea', {
      rows: '14',
      style: 'width: 100%; font-family: monospace; font-size: 12px',
    });
    ta.value = list;
    const body = el('div', {},
      el('div', { class: 'muted xs', style: 'margin-bottom: 8px' },
        'Один сервис на строку: host port name. Например:'),
      el('div', { class: 'mono xs', style: 'margin-bottom: 12px; color: var(--text-dim)' },
        'google.com 443 Google'),
      ta,
      el('div', { class: 'row gap', style: 'margin-top: 14px; justify-content: flex-end' },
        el('button', { class: 'btn ghost', onclick: closeModal }, 'Отмена'),
        el('button', { class: 'btn primary', onclick: async () => {
          const services = ta.value.split('\n').map(l => l.trim()).filter(Boolean)
            .map(line => {
              const parts = line.split(/\s+/);
              const host = parts[0];
              const port = parseInt(parts[1] || '443', 10);
              const name = parts.slice(2).join(' ') || host;
              const kind = port === 53 ? 'dns' : 'web';
              return { host, port, name, kind };
            });
          await API.put('/api/live/services', { services });
          closeModal();
          await this.refresh();
        }}, 'Сохранить'),
      ),
    );
    openModal('Сервисы для live availability', body);
  },

  initUI() {
    $('#live-refresh').addEventListener('click', async () => {
      await this.refreshSys();
      await this.refresh();
    });
    $('#live-autorefresh').addEventListener('change', () => this.startAutoRefresh());
    $('#live-interval').addEventListener('change', () => this.startAutoRefresh());
    $('#live-edit').addEventListener('click', () => this.openEditor());
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
