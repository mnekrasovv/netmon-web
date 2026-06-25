// Monitor tab: batch site checks

const Monitor = {
  categories: [],
  selectedCats: new Set(),
  results: [],
  summary: null,
  currentSSE: null,
  sortKey: 'status',
  sortDir: 1,
  filterText: '',
  chartStatus: null,
  chartCat: null,

  async loadCategories() {
    const data = await API.get('/api/sites');
    this.categories = data.categories;
    // by default — all selected
    this.selectedCats = new Set(this.categories.map(c => c.name));
    this.renderCategories();
  },

  renderCategories() {
    const root = $('#categories-pick');
    root.innerHTML = '';
    this.categories.forEach((c) => {
      const checked = this.selectedCats.has(c.name);
      const lbl = el('label', {},
        el('input', { type: 'checkbox', ...(checked ? { checked: 'checked' } : {}),
          onchange: (e) => {
            if (e.target.checked) this.selectedCats.add(c.name);
            else this.selectedCats.delete(c.name);
          }
        }),
        el('span', {}, c.name.replace(/_/g, ' ')),
        el('span', { class: 'h-name' }, `${c.count} сайтов`),
      );
      root.appendChild(lbl);
    });
  },

  resetStats() {
    ['ok', 'slow', 'warn', 'fail'].forEach(k => $(`#batch-stats [data-stat="${k}"]`).textContent = '0');
    $('#batch-bar').style.width = '0%';
    $('#batch-progress-text').textContent = '0 / 0';
    $('#batch-results tbody').innerHTML = '';
    this.results = [];
    this.summary = null;
  },

  updateStats() {
    const counts = { ok: 0, slow: 0, warn: 0, fail: 0 };
    this.results.forEach(r => { counts[(r.status || 'OK').toLowerCase()] = (counts[(r.status || 'OK').toLowerCase()] || 0) + 1; });
    for (const [k, v] of Object.entries(counts)) {
      const el = $(`#batch-stats [data-stat="${k}"]`);
      if (el) el.textContent = v;
    }
  },

  renderRow(r) {
    const tbody = $('#batch-results tbody');
    const cls = (r.status || 'OK').toLowerCase();
    const loss = r.loss !== undefined ? `${r.loss.toFixed(1)}%` : '—';
    const avg = r.avg != null ? r.avg.toFixed(1) : '—';
    const mx  = r.max != null ? r.max.toFixed(1) : '—';
    let httpCell = 'N/A';
    if (r.http_ok === true) {
      httpCell = `${r.http_status} <span class="muted">${r.http_time_ms || ''}ms</span>`;
    } else if (r.http_ok === false) {
      httpCell = `<span style="color:#e74c3c">ERR</span>`;
    }
    const row = el('tr', { dataset: { name: r.name.toLowerCase(), host: r.host.toLowerCase() } },
      el('td', {}, r.name),
      el('td', { html: `<code>${r.host}</code>` }),
      el('td', { class: 'muted' }, (r.category || '').replace(/_/g, ' ')),
      el('td', {}, loss),
      el('td', {}, avg),
      el('td', {}, mx),
      el('td', { html: httpCell }),
      el('td', { html: `<span class="badge ${cls}">${r.status}</span>` }),
    );
    tbody.appendChild(row);
  },

  rerenderTable() {
    const tbody = $('#batch-results tbody');
    tbody.innerHTML = '';
    let rs = [...this.results];
    if (this.filterText) {
      const q = this.filterText.toLowerCase();
      rs = rs.filter(r => r.name.toLowerCase().includes(q) || r.host.toLowerCase().includes(q));
    }
    const order = { FAIL: 0, WARN: 1, SLOW: 2, OK: 3 };
    rs.sort((a, b) => {
      let va = a[this.sortKey], vb = b[this.sortKey];
      if (this.sortKey === 'status') { va = order[va] ?? 9; vb = order[vb] ?? 9; }
      if (va == null) va = -Infinity;
      if (vb == null) vb = -Infinity;
      if (typeof va === 'string') return this.sortDir * va.localeCompare(vb, 'ru');
      return this.sortDir * (va - vb);
    });
    rs.forEach(r => this.renderRow(r));
  },

  drawCharts() {
    const counts = { OK: 0, SLOW: 0, WARN: 0, FAIL: 0 };
    this.results.forEach(r => counts[r.status] = (counts[r.status] || 0) + 1);

    const byCat = {};
    this.results.forEach(r => {
      const c = (r.category || 'other');
      if (!byCat[c]) byCat[c] = { OK: 0, SLOW: 0, WARN: 0, FAIL: 0 };
      byCat[c][r.status] = (byCat[c][r.status] || 0) + 1;
    });

    if (this.chartStatus) this.chartStatus.destroy();
    this.chartStatus = new Chart($('#chart-status'), {
      type: 'doughnut',
      data: {
        labels: ['OK', 'SLOW', 'WARN', 'FAIL'],
        datasets: [{
          data: [counts.OK, counts.SLOW, counts.WARN, counts.FAIL],
          backgroundColor: ['#2ecc71', '#f39c12', '#e67e22', '#e74c3c'],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#dde' } } },
      },
    });

    if (this.chartCat) this.chartCat.destroy();
    const catLabels = Object.keys(byCat);
    this.chartCat = new Chart($('#chart-cat'), {
      type: 'bar',
      data: {
        labels: catLabels.map(l => l.replace(/_/g, ' ')),
        datasets: [
          { label: 'OK',   data: catLabels.map(l => byCat[l].OK),   backgroundColor: '#2ecc71' },
          { label: 'SLOW', data: catLabels.map(l => byCat[l].SLOW), backgroundColor: '#f39c12' },
          { label: 'WARN', data: catLabels.map(l => byCat[l].WARN), backgroundColor: '#e67e22' },
          { label: 'FAIL', data: catLabels.map(l => byCat[l].FAIL), backgroundColor: '#e74c3c' },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { stacked: true, ticks: { color: '#888' }, grid: { color: '#2a2a40' } },
          y: { stacked: true, ticks: { color: '#888' }, grid: { color: '#2a2a40' }, beginAtZero: true },
        },
        plugins: { legend: { labels: { color: '#dde' } } },
      },
    });
  },

  start() {
    this.resetStats();
    $('#batch-run').disabled = true;
    $('#batch-stop').disabled = false;
    $('#batch-save').disabled = true;

    const cats = [...this.selectedCats].join(',');
    const pingCount = parseInt($('#m-ping-count').value || '5', 10);
    const workers = parseInt($('#m-workers').value || '20', 10);
    const httpTimeout = parseInt($('#m-http-timeout').value || '10', 10);
    const noHttp = $('#m-no-http').checked;

    const url = `/api/stream/batch?categories=${encodeURIComponent(cats)}&ping_count=${pingCount}&workers=${workers}&http_timeout=${httpTimeout}&no_http=${noHttp}`;

    this.currentSSE = openSSE(url, (ev) => {
      if (ev.type === 'meta') {
        $('#batch-progress-text').textContent = `0 / ${ev.payload.total}`;
      } else if (ev.type === 'result') {
        this.results.push(ev.payload);
        this.renderRow(ev.payload);
        this.updateStats();
      } else if (ev.type === 'progress') {
        const pct = (ev.payload.done / ev.payload.total) * 100;
        $('#batch-bar').style.width = `${pct}%`;
        $('#batch-progress-text').textContent = `${ev.payload.done} / ${ev.payload.total}`;
      } else if (ev.type === 'summary') {
        this.summary = ev.payload;
        this.rerenderTable();
        this.drawCharts();
      } else if (ev.type === 'done') {
        $('#batch-run').disabled = false;
        $('#batch-stop').disabled = true;
        $('#batch-save').disabled = !this.summary;
      } else if (ev.type === 'error') {
        // ignore individual errors
      }
    }, () => {
      $('#batch-run').disabled = false;
      $('#batch-stop').disabled = true;
    });
  },

  stop() {
    if (this.currentSSE) {
      this.currentSSE.close();
      this.currentSSE = null;
    }
    $('#batch-run').disabled = false;
    $('#batch-stop').disabled = true;
  },

  async save() {
    if (!this.summary) return;
    const r = await API.post('/api/reports/save-batch-html', { summary: this.summary });
    alert(`Сохранено:\n  ${r.html}\n  ${r.json}`);
    Reports.refresh();
  },

  initUI() {
    $('#batch-run').addEventListener('click', () => this.start());
    $('#batch-stop').addEventListener('click', () => this.stop());
    $('#batch-save').addEventListener('click', () => this.save());
    $('#batch-filter').addEventListener('input', (e) => {
      this.filterText = e.target.value;
      this.rerenderTable();
    });
    $$('#batch-results th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const k = th.dataset.sort;
        if (this.sortKey === k) this.sortDir = -this.sortDir;
        else { this.sortKey = k; this.sortDir = 1; }
        this.rerenderTable();
      });
    });
  },
};
