// Reports tab

const Reports = {
  list: [],

  async refresh() {
    const data = await API.get('/api/reports');
    this.list = data.reports;
    this.render();
    $('#card-reports').textContent = this.list.length;
  },

  render() {
    const tbody = $('#reports-table tbody');
    tbody.innerHTML = '';
    this.list.forEach((r) => {
      const row = el('tr', {},
        el('td', { html: `<code>${r.name}</code>` }),
        el('td', { class: 'muted' }, formatTime(r.mtime)),
        el('td', { class: 'muted' }, formatBytes(r.size)),
        el('td', { class: 'muted' }, r.type),
        el('td', {},
          el('button', { class: 'btn small', onclick: () => this.open(r.name) }, 'открыть'),
          ' ',
          el('a',  { class: 'btn small', href: `/api/reports/${encodeURIComponent(r.name)}/download`, target: '_blank' }, 'скачать'),
          ' ',
          el('button', { class: 'btn small danger', onclick: async () => {
            if (!confirm(`Удалить ${r.name}?`)) return;
            await API.del(`/api/reports/${encodeURIComponent(r.name)}`);
            await this.refresh();
          }}, '×'),
        ),
      );
      tbody.appendChild(row);
    });
  },

  async open(name) {
    let body;
    if (name.endsWith('.html')) {
      body = el('iframe', { src: `/api/reports/${encodeURIComponent(name)}` });
    } else if (name.endsWith('.json')) {
      const r = await fetch(`/api/reports/${encodeURIComponent(name)}`);
      const j = await r.json();
      body = el('pre', {}, JSON.stringify(j, null, 2));
    } else {
      const r = await fetch(`/api/reports/${encodeURIComponent(name)}`);
      const t = await r.text();
      body = el('pre', {}, t);
    }
    openModal(name, body);
  },

  initUI() {
    $('#reports-refresh').addEventListener('click', () => this.refresh());
  },
};
