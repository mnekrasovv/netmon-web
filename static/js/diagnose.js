// Diagnose tab: select hosts, select tests, run, stream output

const Diagnose = {
  customHosts: [],   // [{host, name, cat}]
  selectedHostIdxs: new Set(), // indices into combined list
  bufferLines: [],
  currentSSE: null,
  runQueue: [],

  combinedHosts() {
    return [...Hosts.cache, ...this.customHosts];
  },

  renderHostsList() {
    const root = $('#hosts-pick');
    root.innerHTML = '';
    this.combinedHosts().forEach((h, i) => {
      const checked = this.selectedHostIdxs.has(i);
      const lbl = el('label', {},
        el('input', { type: 'checkbox', ...(checked ? { checked: 'checked' } : {}),
          onchange: (e) => {
            if (e.target.checked) this.selectedHostIdxs.add(i);
            else this.selectedHostIdxs.delete(i);
          }
        }),
        el('span', {}, h.host),
        el('span', { class: 'h-name' }, h.name || ''),
        el('span', { class: 'h-cat' }, h.cat || ''),
      );
      root.appendChild(lbl);
    });
  },

  addCustomHost(input) {
    const v = input.trim();
    if (!v) return;
    this.customHosts.push({ host: v, name: v, cat: 'custom' });
    this.renderHostsList();
  },

  selectedTests() {
    return $$('#panel-diagnose [data-test]:checked').map(c => c.dataset.test);
  },

  selectedHosts() {
    return [...this.selectedHostIdxs].sort((a, b) => a - b).map(i => this.combinedHosts()[i]).filter(Boolean);
  },

  appendLine(line) {
    this.bufferLines.push(line);
    const c = $('#diag-console');
    c.textContent += line + '\n';
    c.scrollTop = c.scrollHeight;
  },

  appendHeader(title) {
    const sep = '─'.repeat(Math.max(2, 46 - title.length - 2));
    this.appendLine('');
    this.appendLine(`── ${title} ${sep}`);
    this.appendLine('');
  },

  setStatus(text, cls) {
    const s = $('#diag-status');
    s.textContent = text;
    s.className = 'diag-status' + (cls ? ' ' + cls : '');
  },

  clear() {
    this.bufferLines = [];
    $('#diag-console').textContent = '';
    this.setStatus('готов');
    $('#diag-save').disabled = true;
  },

  stop() {
    if (this.currentSSE) {
      this.currentSSE.close();
      this.currentSSE = null;
    }
    this.runQueue = [];
    $('#diag-run').disabled = false;
    $('#diag-stop').disabled = true;
    this.setStatus('остановлено');
  },

  async runNext() {
    if (this.runQueue.length === 0) {
      $('#diag-run').disabled = false;
      $('#diag-stop').disabled = true;
      $('#diag-save').disabled = this.bufferLines.length === 0;
      this.setStatus('готово', 'done');
      return;
    }
    const task = this.runQueue.shift();
    this.setStatus(`выполняется: ${task.label}`, 'running');
    this.appendHeader(task.label);

    return new Promise((resolve) => {
      this.currentSSE = openSSE(task.url, (ev) => {
        if (ev.type === 'line') this.appendLine(ev.payload);
        else if (ev.type === 'done') {
          this.currentSSE = null;
          this.runNext().then(resolve);
        } else if (ev.type === 'error') {
          this.appendLine(`[error] ${ev.payload}`);
        }
      }, (e) => {
        this.appendLine('[stream error]');
        this.currentSSE = null;
        this.runNext().then(resolve);
      });
    });
  },

  async run() {
    const tests = this.selectedTests();
    const hosts = this.selectedHosts();
    if (tests.length === 0) {
      alert('Выберите хотя бы один тест');
      return;
    }
    const needHosts = tests.some(t => ['ping', 'trace', 'mtr', 'http'].includes(t));
    if (needHosts && hosts.length === 0) {
      alert('Выберите хотя бы один хост для выбранных тестов');
      return;
    }

    this.bufferLines = [];
    $('#diag-console').textContent = '';
    $('#diag-save').disabled = true;
    $('#diag-run').disabled = true;
    $('#diag-stop').disabled = false;

    const pingCount = parseInt($('#ping-count').value || '10', 10);
    const mtrCycles = parseInt($('#mtr-cycles').value || '10', 10);

    this.appendLine(`netmon-web · диагностика · ${new Date().toLocaleString('ru-RU')}`);

    const q = [];
    for (const t of tests) {
      if (t === 'ping') {
        for (const h of hosts) q.push({ label: `Ping → ${h.host} (${h.name})`, url: `/api/stream/ping?host=${encodeURIComponent(h.host)}&count=${pingCount}` });
      } else if (t === 'trace') {
        for (const h of hosts) q.push({ label: `Traceroute → ${h.host} (${h.name})`, url: `/api/stream/trace?host=${encodeURIComponent(h.host)}` });
      } else if (t === 'mtr') {
        for (const h of hosts) q.push({ label: `MTR → ${h.host} (${h.name})`, url: `/api/stream/mtr?host=${encodeURIComponent(h.host)}&cycles=${mtrCycles}` });
      } else if (t === 'http') {
        for (const h of hosts) q.push({ label: `HTTP → ${h.host}`, url: `/api/stream/http?url=${encodeURIComponent(h.host)}` });
      } else if (t === 'dns') {
        q.push({ label: 'DNS диагностика', url: '/api/stream/dns' });
      } else if (t === 'external-ip') {
        q.push({ label: 'Внешний IP', url: '/api/stream/external-ip' });
      } else if (t === 'sysinfo') {
        q.push({ label: 'Система', url: '/api/stream/sysinfo' });
      } else if (t === 'interfaces') {
        q.push({ label: 'Интерфейсы', url: '/api/stream/interfaces' });
      } else if (t === 'connections') {
        q.push({ label: 'Соединения', url: '/api/stream/connections' });
      } else if (t === 'arp') {
        q.push({ label: 'ARP', url: '/api/stream/arp' });
      }
    }
    this.runQueue = q;
    await this.runNext();
  },

  async save() {
    if (this.bufferLines.length === 0) return;
    const r = await API.post('/api/reports/save', {
      prefix: 'diag',
      lines: this.bufferLines,
    });
    alert(`Сохранено: ${r.name}`);
    Reports.refresh();
  },

  initUI() {
    $('#diag-run').addEventListener('click', () => this.run());
    $('#diag-stop').addEventListener('click', () => this.stop());
    $('#diag-clear').addEventListener('click', () => this.clear());
    $('#diag-save').addEventListener('click', () => this.save());
    $('#add-custom-host').addEventListener('click', () => {
      const inp = $('#custom-host-input');
      this.addCustomHost(inp.value);
      inp.value = '';
    });
    $('#custom-host-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.addCustomHost(e.target.value);
        e.target.value = '';
      }
    });
  },
};
