// Hosts tab + provides list for diagnose tab

const Hosts = {
  cache: [],

  async load() {
    const data = await API.get('/api/hosts');
    this.cache = data.hosts;
    return this.cache;
  },

  async add(host, name, cat) {
    return API.post('/api/hosts', { host, name, cat });
  },

  async remove(idx) {
    return API.del(`/api/hosts/${idx}`);
  },

  async update(idx, host, name, cat) {
    return API.put(`/api/hosts/${idx}`, { host, name, cat });
  },

  render() {
    const tbody = $('#hosts-table tbody');
    tbody.innerHTML = '';
    this.cache.forEach((h, i) => {
      const row = el('tr', {},
        el('td', {}, String(i + 1)),
        el('td', { html: `<code>${h.host}</code>` }),
        el('td', {}, h.name || ''),
        el('td', { html: `<span class="muted">${h.cat || ''}</span>` }),
        el('td', {},
          el('button', { class: 'btn small danger', onclick: async () => {
            if (!confirm(`Удалить хост ${h.host}?`)) return;
            await this.remove(i);
            await this.load();
            this.render();
            Diagnose.renderHostsList();
          }}, '×')
        ),
      );
      tbody.appendChild(row);
    });
  },

  initUI() {
    $('#h-add').addEventListener('click', async () => {
      const host = $('#h-input-host').value.trim();
      const name = $('#h-input-name').value.trim();
      const cat  = $('#h-input-cat').value;
      if (!host) return;
      await this.add(host, name, cat);
      $('#h-input-host').value = '';
      $('#h-input-name').value = '';
      await this.load();
      this.render();
      Diagnose.renderHostsList();
    });
  },
};
