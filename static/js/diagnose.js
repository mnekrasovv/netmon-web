// Diagnose tab: parsed + raw outputs, suggestions

const Diagnose = {
  customHosts: [],
  selectedHostIdxs: new Set(),
  bufferLines: [],   // raw lines for save
  parsedResults: [], // structured results
  currentSSE: null,
  runQueue: [],
  viewMode: 'parsed',

  combinedHosts() { return [...Hosts.cache, ...this.customHosts]; },

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
          }}),
        el('span', {}, h.host),
        el('span', { class: 'h-name' }, h.name || ''),
        el('span', { class: 'h-cat' }, h.cat || ''),
      );
      root.appendChild(lbl);
    });
  },

  addCustomHost(input) {
    const v = (input || '').trim();
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

  appendSection(title) {
    this.bufferLines.push('', `── ${title} ──`, '');
    const sep = el('div', { class: 'res-section' },
      el('div', { class: 'res-section-title' }, title),
      el('div', { class: 'res-content', id: `sec-${slug(title)}` }),
    );
    $('#diag-results-parsed').appendChild(sep);
    return $(`#sec-${slug(title)}`);
  },

  appendParsed(node) {
    const sec = $('#diag-results-parsed').lastChild;
    if (!sec) return;
    const content = sec.querySelector('.res-content');
    content.appendChild(node);
    sec.scrollIntoView({ block: 'nearest' });
  },

  setStatus(text, cls) {
    const s = $('#diag-status');
    s.textContent = text;
    s.className = 'diag-status xs muted' + (cls ? ' ' + cls : '');
  },

  clear() {
    this.bufferLines = [];
    this.parsedResults = [];
    $('#diag-console').textContent = '';
    $('#diag-results-parsed').innerHTML = '';
    $('#diag-suggestions').innerHTML = '';
    $('#diag-suggestions-block').hidden = true;
    this.setStatus('готов');
    $('#diag-save').disabled = true;
  },

  stop() {
    if (this.currentSSE) { this.currentSSE.close(); this.currentSSE = null; }
    this.runQueue = [];
    $('#diag-run').disabled = false;
    $('#diag-stop').disabled = true;
    this.setStatus('остановлено');
  },

  // Tasks are objects: {label, kind, host?, name?, params?, target?}
  async runNext() {
    if (this.runQueue.length === 0) {
      $('#diag-run').disabled = false;
      $('#diag-stop').disabled = true;
      $('#diag-save').disabled = this.bufferLines.length === 0;
      this.setStatus('готово', 'done');
      await this.showSuggestions();
      return;
    }
    const task = this.runQueue.shift();
    this.setStatus(`выполняется: ${task.label}`, 'running');
    const section = this.appendSection(task.label);

    try {
      await this.runTask(task, section);
    } catch (e) {
      this.appendLine(`[error] ${e}`);
    }
    return this.runNext();
  },

  async runTask(task, section) {
    const t = task.kind;
    if (t === 'ping') {
      // Raw stream + parsed at end
      await this.streamAndCapture(`/api/stream/ping?host=${encodeURIComponent(task.host)}&count=${task.params.count}`);
      const r = await API.get(`/api/parsed/ping?host=${encodeURIComponent(task.host)}&count=${task.params.count}`);
      const node = Render.ping({ ...r.parsed, host: task.host, name: task.name });
      section.appendChild(node);
      this.parsedResults.push({ type: 'ping', ...r.parsed, name: task.name });
    } else if (t === 'trace') {
      await this.streamAndCapture(`/api/stream/trace?host=${encodeURIComponent(task.host)}`);
      const r = await API.get(`/api/parsed/trace?host=${encodeURIComponent(task.host)}`);
      section.appendChild(Render.trace(r.parsed || [], task.host));
      this.parsedResults.push({ type: 'trace', host: task.host, hops: r.parsed });
    } else if (t === 'mtr') {
      this.appendLine('Запуск MTR (parsed)...');
      const r = await API.get(`/api/parsed/mtr?host=${encodeURIComponent(task.host)}&cycles=${task.params.cycles}`);
      section.appendChild(Render.mtr(task.host, r.hops || []));
      this.parsedResults.push({ type: 'mtr', host: task.host, hops: r.hops });
      this.appendLine(`MTR: ${(r.hops || []).length} хопов`);
    } else if (t === 'http') {
      await this.streamAndCapture(`/api/stream/http?url=${encodeURIComponent(task.host)}`);
      const r = await API.get(`/api/parsed/http?url=${encodeURIComponent(task.host)}`);
      section.appendChild(Render.http(r));
      this.parsedResults.push({ type: 'http', ...r });
    } else if (t === 'dns') {
      this.appendLine('Загрузка DNS-матрицы...');
      const matrix = await API.get('/api/dns/matrix');
      const pings  = await API.get('/api/dns/pings');
      section.appendChild(Render.dns(matrix));
      this.parsedResults.push({ type: 'dns', matrix, pings: pings.pings });
    } else if (t === 'external-ip') {
      this.appendLine('Получение внешнего IP...');
      const r = await API.get('/api/external-ip');
      section.appendChild(Render.external_ip(r));
      this.parsedResults.push({ type: 'external_ip', ...r });
      // Append console lines from stream too:
      await this.streamAndCapture('/api/stream/external-ip');
    } else if (t === 'sysinfo') {
      const r = await API.get('/api/sysinfo');
      section.appendChild(Render.sysinfo(r));
      this.parsedResults.push({ type: 'sysinfo', ...r });
    } else if (t === 'interfaces') {
      const r = await API.get('/api/parsed/interfaces');
      section.appendChild(Render.interfaces(r.interfaces || []));
      this.parsedResults.push({ type: 'interfaces', interfaces: r.interfaces });
      if (r.raw) (r.raw.split('\n')).slice(0, 200).forEach(l => this.bufferLines.push(l));
    } else if (t === 'connections') {
      const r = await API.get('/api/parsed/connections');
      section.appendChild(Render.connections(r.connections || []));
      this.parsedResults.push({ type: 'connections', count: (r.connections || []).length });
    }
  },

  streamAndCapture(url) {
    return new Promise((resolve) => {
      this.currentSSE = openSSE(url, (ev) => {
        if (ev.type === 'line') this.appendLine(ev.payload);
        else if (ev.type === 'done') { this.currentSSE = null; resolve(); }
        else if (ev.type === 'error') this.appendLine(`[error] ${ev.payload}`);
      }, () => { this.currentSSE = null; resolve(); });
    });
  },

  async run() {
    const tests = this.selectedTests();
    const hosts = this.selectedHosts();
    if (tests.length === 0) { alert('Выберите хотя бы один тест'); return; }
    const needHosts = tests.some(t => ['ping', 'trace', 'mtr', 'http'].includes(t));
    if (needHosts && hosts.length === 0) { alert('Выберите хотя бы один хост'); return; }

    this.clear();
    $('#diag-run').disabled = true;
    $('#diag-stop').disabled = false;

    const pingCount = parseInt($('#ping-count').value || '10', 10);
    const mtrCycles = parseInt($('#mtr-cycles').value || '10', 10);

    this.bufferLines.push(`netmon · diagnose · ${new Date().toLocaleString('ru-RU')}`);

    const q = [];
    for (const t of tests) {
      if (t === 'ping')        hosts.forEach(h => q.push({ kind: 'ping',  host: h.host, name: h.name, label: `Ping → ${h.host}`,        params: { count: pingCount }}));
      else if (t === 'trace')  hosts.forEach(h => q.push({ kind: 'trace', host: h.host, name: h.name, label: `Traceroute → ${h.host}`, params: {} }));
      else if (t === 'mtr')    hosts.forEach(h => q.push({ kind: 'mtr',   host: h.host, name: h.name, label: `MTR → ${h.host}`,         params: { cycles: mtrCycles }}));
      else if (t === 'http')   hosts.forEach(h => q.push({ kind: 'http',  host: h.host, name: h.name, label: `HTTP → ${h.host}`,        params: {} }));
      else if (t === 'dns')         q.push({ kind: 'dns',         label: 'DNS матрица',  params: {} });
      else if (t === 'external-ip') q.push({ kind: 'external-ip', label: 'Внешний IP',   params: {} });
      else if (t === 'sysinfo')     q.push({ kind: 'sysinfo',     label: 'Система',      params: {} });
      else if (t === 'interfaces')  q.push({ kind: 'interfaces',  label: 'Интерфейсы',   params: {} });
      else if (t === 'connections') q.push({ kind: 'connections', label: 'Соединения',   params: {} });
    }
    this.runQueue = q;
    await this.runNext();
  },

  async showSuggestions() {
    if (this.parsedResults.length === 0) return;
    const payload = this.buildSuggestionsPayload();
    const r = await API.post('/api/suggestions', payload);
    const root = $('#diag-suggestions');
    root.innerHTML = '';
    (r.suggestions || []).forEach(s => {
      const node = el('div', { class: `sugg ${s.level}` },
        el('div', {},
          el('div', { class: 'sugg-title' }, s.title),
          el('div', { class: 'sugg-body' }, s.body),
        ),
      );
      root.appendChild(node);
    });
    $('#diag-suggestions-block').hidden = false;
  },

  buildSuggestionsPayload() {
    const ping = this.parsedResults.filter(r => r.type === 'ping').map(r => ({
      host: r.host, name: r.name, avg: r.avg, loss: r.loss, ok: r.ok, sent: r.sent, recv: r.recv,
    }));
    const trace = (this.parsedResults.find(r => r.type === 'trace') || {}).hops;
    const mtr   = (this.parsedResults.find(r => r.type === 'mtr')   || {}).hops;
    const dnsResult = this.parsedResults.find(r => r.type === 'dns');
    const http  = this.parsedResults.filter(r => r.type === 'http').map(r => ({ url: r.url, ok: r.ok, status: r.status, time_ms: r.time_ms, error: r.error }));
    const ext   = this.parsedResults.find(r => r.type === 'external_ip');
    return {
      ping,
      trace,
      mtr,
      dns_matrix: dnsResult ? dnsResult.matrix : null,
      dns_server_pings: dnsResult ? dnsResult.pings : null,
      http,
      external_ip: ext,
    };
  },

  async save() {
    if (!this.bufferLines.length && !this.parsedResults.length) return;
    // Save txt (raw)
    const txt = await API.post('/api/reports/save', { prefix: 'diag', lines: this.bufferLines });
    // Save json (parsed)
    const json = await API.post('/api/reports/save-json', {
      prefix: 'diag',
      data: { ts: new Date().toISOString(), results: this.parsedResults },
    });
    alert(`Сохранено:\n  ${txt.name}\n  ${json.name}`);
    Reports.refresh();
  },

  switchView(mode) {
    this.viewMode = mode;
    $$('.seg-btn').forEach(b => b.classList.toggle('active', b.dataset.view === mode));
    $('#diag-results-parsed').hidden = mode !== 'parsed';
    $('#diag-console').hidden        = mode !== 'raw';
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
        this.addCustomHost(e.target.value); e.target.value = '';
      }
    });
    $$('.seg-btn').forEach(b => b.addEventListener('click', () => this.switchView(b.dataset.view)));
  },
};

function slug(s) { return (s || '').replace(/[^a-zа-я0-9]/gi, '_').toLowerCase(); }
