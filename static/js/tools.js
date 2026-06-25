// Tools tab: TCP port checker, nslookup, whois

const Tools = {
  presets: {},

  async loadPresets() {
    this.presets = await API.get('/api/tcp/presets');
    const root = $('#tcp-presets');
    root.innerHTML = '';
    Object.entries(this.presets).forEach(([name, port]) => {
      const chip = el('span', { class: 'preset-chip', onclick: () => {
        const inp = $('#tcp-ports');
        inp.value = inp.value ? `${inp.value}, ${name}` : name;
      }}, `${name}:${port}`);
      root.appendChild(chip);
    });
  },

  async checkTCP() {
    const host = $('#tcp-host').value.trim();
    const ports = $('#tcp-ports').value.trim();
    if (!host || !ports) return;
    const root = $('#tcp-result');
    root.innerHTML = '<div class="muted xs">проверяю...</div>';
    try {
      const r = await API.get(`/api/tcp?host=${encodeURIComponent(host)}&ports=${encodeURIComponent(ports)}`);
      this.renderTCP(r, root);
    } catch (e) {
      root.innerHTML = '';
      root.appendChild(el('div', { class: 'sugg error' }, el('div', { class: 'sugg-title' }, 'Ошибка'), el('div', { class: 'sugg-body' }, String(e))));
    }
  },

  renderTCP(r, root) {
    root.innerHTML = '';
    const grid = el('div', { class: 'tcp-grid' });
    r.results.forEach(p => {
      const svc = Object.entries(this.presets).find(([_, port]) => port === p.port);
      const cls = p.open ? 'open' : 'closed';
      grid.appendChild(el('div', { class: `tcp-tile ${cls}` },
        el('div', { class: 'tcp-port-num' }, String(p.port)),
        el('div', { class: 'tcp-port-svc' }, svc ? svc[0] : '—'),
        el('div', { class: 'tcp-port-status' },
          el('span', { class: `badge ${p.open ? 'ok' : 'fail'}` }, p.open ? 'OPEN' : 'CLOSED'),
          ' ',
          el('span', { class: 'muted xs' }, p.time_ms != null ? `${p.time_ms}ms` : (p.error || '')),
        ),
      ));
    });
    root.appendChild(grid);
  },

  async nslookup() {
    const host = $('#ns-host').value.trim();
    const server = $('#ns-server').value.trim();
    const type = $('#ns-type').value;
    if (!host) return;
    const root = $('#ns-result');
    root.innerHTML = '<div class="muted xs">резолвлю...</div>';
    try {
      const r = await API.get(`/api/nslookup?host=${encodeURIComponent(host)}&server=${encodeURIComponent(server)}&type=${type}`);
      this.renderNS(r, root);
    } catch (e) {
      root.innerHTML = '';
      root.appendChild(el('div', { class: 'sugg error' }, el('div', { class: 'sugg-title' }, 'Ошибка'), el('div', { class: 'sugg-body' }, String(e))));
    }
  },

  renderNS(r, root) {
    root.innerHTML = '';
    if (r.reverse_dns) {
      root.appendChild(el('div', { class: 'host-card' },
        el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' }, 'Reverse DNS')),
        el('div', { class: 'mono' }, r.reverse_dns),
      ));
    }
    const tbl = el('table', { class: 'hop-table' });
    tbl.appendChild(el('thead', {}, el('tr', {},
      el('th', {}, 'Тип'),
      el('th', {}, 'Значение'),
      el('th', {}, 'Доп.'),
    )));
    const tbody = el('tbody');
    (r.records || []).forEach(rec => {
      tbody.appendChild(el('tr', {},
        el('td', {}, rec.type),
        el('td', { class: 'ip' }, rec.value),
        el('td', { class: 'muted xs' }, rec.priority != null ? `priority=${rec.priority}` : ''),
      ));
    });
    if (!(r.records || []).length) {
      tbody.appendChild(el('tr', {}, el('td', { colspan: '3', class: 'muted' }, 'Записей не найдено')));
    }
    tbl.appendChild(tbody);
    root.appendChild(el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' }, `DNS records (${r.server || 'system'})`)),
      tbl,
    ));

    if (r.raw) {
      const det = el('details', {},
        el('summary', { class: 'muted xs', style: 'cursor:pointer; margin-top:8px' }, 'Сырой ответ'),
        el('pre', { style: 'background: var(--code-bg); padding: 8px; border-radius:6px; margin-top:6px; color: #d0d4e6; font-size: 11px; white-space: pre-wrap' }, r.raw),
      );
      root.appendChild(det);
    }
  },

  async whois() {
    const host = $('#whois-host').value.trim();
    if (!host) return;
    const root = $('#whois-result');
    root.innerHTML = '<div class="muted xs">whois запрос...</div>';
    try {
      const r = await API.get(`/api/whois?host=${encodeURIComponent(host)}`);
      this.renderWhois(r, root);
    } catch (e) {
      root.innerHTML = '';
      root.appendChild(el('div', { class: 'sugg error' }, el('div', { class: 'sugg-title' }, 'Ошибка'), el('div', { class: 'sugg-body' }, String(e))));
    }
  },

  renderWhois(r, root) {
    root.innerHTML = '';
    const p = r.parsed || {};
    const fields = [
      ['Сервер',         r.server],
      ['Registrar',      p.registrar],
      ['Organization',   p.organization],
      ['Country',        p.country],
      ['City',           p.city],
      ['ASN',            p.asn],
      ['NetName',        p.netname],
      ['CIDR',           p.cidr],
      ['Created',        p.created],
      ['Updated',        p.updated],
      ['Expires',        p.expires],
      ['Name servers',   p.name_servers && p.name_servers.join(', ')],
    ];
    const grid = el('div', { class: 'whois-grid' });
    let anyShown = false;
    fields.forEach(([k, v]) => {
      if (v) {
        grid.appendChild(el('div', { class: 'k' }, k));
        grid.appendChild(el('div', {}, String(v)));
        anyShown = true;
      }
    });
    root.appendChild(el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' }, 'Whois')),
      anyShown ? grid : el('div', { class: 'muted xs' }, 'Структурированных полей не найдено — смотрите сырой ответ ниже'),
    ));
    if (r.raw) {
      root.appendChild(el('details', {},
        el('summary', { class: 'muted xs', style: 'cursor:pointer; margin-top: 8px' }, 'Сырой ответ whois'),
        el('pre', { style: 'background: var(--code-bg); padding: 10px; border-radius:6px; margin-top:6px; color: #d0d4e6; font-size: 11px; white-space: pre-wrap; max-height: 400px; overflow:auto' }, r.raw),
      ));
    }
  },

  initUI() {
    $('#tcp-check').addEventListener('click', () => this.checkTCP());
    $('#tcp-host').addEventListener('keydown',  e => { if (e.key === 'Enter') this.checkTCP(); });
    $('#tcp-ports').addEventListener('keydown', e => { if (e.key === 'Enter') this.checkTCP(); });
    $('#ns-check').addEventListener('click', () => this.nslookup());
    $('#ns-host').addEventListener('keydown', e => { if (e.key === 'Enter') this.nslookup(); });
    $('#whois-check').addEventListener('click', () => this.whois());
    $('#whois-host').addEventListener('keydown', e => { if (e.key === 'Enter') this.whois(); });
  },
};
