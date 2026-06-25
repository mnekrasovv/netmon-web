// Version display + update check

const Version = {
  data: null,

  async load() {
    try {
      this.data = await API.get('/api/version');
    } catch {
      this.data = { current: '?.?.?' };
    }
    this.render();
  },

  render() {
    const txt = $('#version-text');
    const upd = $('#version-update');
    if (!this.data) return;
    txt.textContent = `v${this.data.current}`;
    if (this.data.update_available && this.data.latest) {
      txt.style.color = 'var(--warn)';
      upd.hidden = false;
      upd.textContent = `→ ${this.data.latest}`;
      upd.title = 'Доступно обновление, нажмите чтобы посмотреть';
      upd.onclick = (e) => { e.preventDefault(); this.showUpdateModal(); };
    } else {
      txt.style.color = '';
      upd.hidden = true;
    }
  },

  showUpdateModal() {
    const d = this.data;
    const body = el('div', {},
      el('div', { class: 'host-card-grid', style: 'margin-bottom: 12px' },
        kv('Текущая', `v${d.current}`),
        kv('Доступна', d.latest),
      ),
      d.release_notes ? el('div', {},
        el('div', { class: 'muted xs', style: 'margin-bottom: 6px' }, 'Что нового:'),
        el('pre', { style: 'background: var(--code-bg); padding: 10px; border-radius: 6px; color: #d0d4e6; font-size: 12px; white-space: pre-wrap; max-height: 280px; overflow:auto' }, d.release_notes),
      ) : null,
      el('div', { class: 'muted xs', style: 'margin-top: 12px' },
        'Чтобы обновиться: закройте приложение и запустите install-команду из README снова. Конфиги (hosts, sites) и отчёты сохранятся.'),
      el('div', { class: 'row gap', style: 'margin-top: 14px; justify-content: flex-end' },
        el('button', { class: 'btn ghost', onclick: closeModal }, 'Закрыть'),
        el('a', { class: 'btn primary', href: d.release_url, target: '_blank' }, 'Открыть на GitHub'),
      ),
    );
    openModal(`Обновление до ${d.latest}`, body);
  },
};
