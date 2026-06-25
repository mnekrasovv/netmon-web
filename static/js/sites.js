// Sites editor: full CRUD over sites.json

const Sites = {
  data: { categories: {} },

  async load() {
    this.data = await API.get('/api/sites/all');
    this.render();
  },

  render() {
    const root = $('#sites-editor');
    root.innerHTML = '';
    const cats = this.data.categories || {};
    const names = Object.keys(cats);
    if (names.length === 0) {
      root.appendChild(el('div', { class: 'muted xs' }, 'Категорий нет — добавьте первую'));
      return;
    }
    names.forEach(catName => {
      const sites = cats[catName] || [];
      const block = el('div', { class: 'cat-block' },
        el('div', { class: 'cat-head' },
          el('div', { class: 'cat-name' },
            catName.replace(/_/g, ' '),
            el('span', { class: 'cat-count' }, `${sites.length} сайтов`),
          ),
          el('div', { class: 'cat-actions' },
            el('button', { class: 'btn small ghost', onclick: () => this.bulkAdd(catName) }, 'Bulk'),
            el('button', { class: 'btn small ghost', onclick: () => this.renameCat(catName) }, 'Rename'),
            el('button', { class: 'btn small danger', onclick: () => this.delCat(catName) }, '×'),
          ),
        ),
        this.renderSites(catName, sites),
        this.renderAddRow(catName),
      );
      root.appendChild(block);
    });
  },

  renderSites(catName, sites) {
    const wrap = el('div', { class: 'cat-sites' });
    sites.forEach((s, idx) => {
      wrap.appendChild(el('div', { class: 'site-row' },
        el('span', { class: 'site-host' }, s.host),
        el('span', { class: 'site-name' }, s.name || s.host),
        el('span', { class: 'site-x',
          onclick: async () => {
            await API.del(`/api/sites/categories/${encodeURIComponent(catName)}/sites/${idx}`);
            await this.load();
            Monitor.loadCategories();
          }
        }, '×'),
      ));
    });
    return wrap;
  },

  renderAddRow(catName) {
    const hi = el('input', { type: 'text', placeholder: 'host', class: 'grow' });
    const ni = el('input', { type: 'text', placeholder: 'имя (опц.)', class: 'grow' });
    const btn = el('button', { class: 'btn small primary' }, '+ сайт');
    btn.addEventListener('click', async () => {
      const host = hi.value.trim();
      if (!host) return;
      await API.post(`/api/sites/categories/${encodeURIComponent(catName)}/sites`, { host, name: ni.value.trim() });
      hi.value = ''; ni.value = '';
      await this.load();
      Monitor.loadCategories();
    });
    return el('div', { class: 'cat-add-row' }, hi, ni, btn);
  },

  async addCategory() {
    const name = prompt('Имя категории (snake_case, без пробелов):');
    if (!name) return;
    try { await API.post('/api/sites/categories', { name }); } catch (e) { alert('Не удалось добавить (имя занято?)'); return; }
    await this.load();
    Monitor.loadCategories();
  },

  async delCat(name) {
    if (!confirm(`Удалить категорию «${name}» вместе со всеми сайтами?`)) return;
    await API.del(`/api/sites/categories/${encodeURIComponent(name)}`);
    await this.load();
    Monitor.loadCategories();
  },

  async renameCat(name) {
    const next = prompt('Новое имя категории:', name);
    if (!next || next === name) return;
    try { await API.put(`/api/sites/categories/${encodeURIComponent(name)}`, { new: next }); } catch { alert('Не удалось переименовать'); return; }
    await this.load();
    Monitor.loadCategories();
  },

  bulkAdd(catName) {
    const ta = el('textarea', { rows: '8', style: 'width:100%' });
    ta.placeholder = 'Один сайт на строку:\nhost\nhost name\nhost name with spaces';
    const modal = openModal(`Bulk import → ${catName}`, ta);
    const footer = el('div', { class: 'row gap', style: 'margin-top: 12px; justify-content: flex-end' },
      el('button', { class: 'btn ghost', onclick: closeModal }, 'Отмена'),
      el('button', { class: 'btn primary', onclick: async () => {
        const r = await API.post(`/api/sites/categories/${encodeURIComponent(catName)}/bulk`, { text: ta.value });
        closeModal();
        alert(`Добавлено: ${r.added}`);
        await this.load();
        Monitor.loadCategories();
      }}, 'Импорт'),
    );
    modal.body.appendChild(footer);
  },

  async reset() {
    if (!confirm('Сбросить sites.json к дефолтной версии?')) return;
    try { await API.post('/api/sites/reset', {}); } catch { alert('Дефолт не найден (старая версия конфига).'); return; }
    await this.load();
    Monitor.loadCategories();
  },

  initUI() {
    $('#sites-new-cat').addEventListener('click', () => this.addCategory());
    $('#sites-reset').addEventListener('click', () => this.reset());
  },
};
