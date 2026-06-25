// Renderers: parsed result -> DOM

const Render = {
  ping(parsed) {
    const status = statusFromPing(parsed);
    const grid = el('div', { class: 'host-card-grid' });
    grid.appendChild(kv('Sent', parsed.sent));
    grid.appendChild(kv('Recv', parsed.recv));
    grid.appendChild(kv('Loss',  pct(parsed.loss)));
    grid.appendChild(kv('Avg',  ms(parsed.avg)));
    grid.appendChild(kv('Min',  ms(parsed.min)));
    grid.appendChild(kv('Max',  ms(parsed.max)));
    grid.appendChild(kv('Jitter', ms(parsed.jitter)));

    const card = el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' },
        el('div', { class: 'host-card-title' },
          el('span', { class: `dot ${status.toLowerCase()}` }),
          parsed.host,
        ),
        badge(status),
      ),
      grid,
    );

    if (parsed.times && parsed.times.length > 1) {
      const canvas = el('canvas');
      const wrap = el('div', { class: 'host-card-spark' }, canvas);
      card.appendChild(wrap);
      setTimeout(() => drawSpark(canvas, parsed.times), 10);
    }
    return card;
  },

  trace(hops, host) {
    const tbl = el('table', { class: 'hop-table' });
    const thead = el('thead', {}, el('tr', {},
      el('th', {}, '#'),
      el('th', {}, 'IP'),
      el('th', {}, 'RTT (avg)'),
      el('th', {}, 'Все измерения'),
    ));
    const tbody = el('tbody');
    hops.forEach(h => {
      const ip = h.ip ? el('span', { class: 'ip' }, h.ip) : el('span', { class: 'timeout' }, '* * *');
      const rtts = h.rtts && h.rtts.length ? h.rtts.map(x => `${x}ms`).join('  ') : '—';
      const avg = h.avg_rtt != null ? `${h.avg_rtt}ms` : '—';
      tbody.appendChild(el('tr', {},
        el('td', { class: 'num' }, String(h.hop)),
        el('td', {}, ip),
        el('td', {}, avg),
        el('td', { class: 'muted xs' }, rtts),
      ));
    });
    tbl.appendChild(thead);
    tbl.appendChild(tbody);
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' },
        el('div', { class: 'host-card-title' }, `Traceroute → ${host}`),
      ),
      tbl,
    );
  },

  mtr(target, hops) {
    const tbl = el('table', { class: 'hop-table' });
    tbl.appendChild(el('thead', {}, el('tr', {},
      el('th', {}, '#'),
      el('th', {}, 'IP'),
      el('th', {}, 'Loss'),
      el('th', {}, 'Sent'),
      el('th', {}, 'Recv'),
      el('th', {}, 'Avg'),
      el('th', {}, 'Min'),
      el('th', {}, 'Max'),
    )));
    const tbody = el('tbody');
    hops.forEach(h => {
      const ip = h.ip ? el('span', { class: 'ip' }, h.ip) : el('span', { class: 'timeout' }, '* * *');
      const lossBar = el('span', { class: 'loss-bar' }, el('span', { style: `width: ${Math.min(100, h.loss || 0)}%` }));
      tbody.appendChild(el('tr', {},
        el('td', { class: 'num' }, String(h.hop)),
        el('td', {}, ip),
        el('td', {},
          el('span', {}, h.loss != null ? `${h.loss.toFixed(1)}%` : '—'),
          h.ip ? lossBar : null,
        ),
        el('td', {}, String(h.sent || 0)),
        el('td', {}, String(h.recv || 0)),
        el('td', {}, ms(h.avg)),
        el('td', {}, ms(h.min)),
        el('td', {}, ms(h.max)),
      ));
    });
    tbl.appendChild(tbody);
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' },
        el('div', { class: 'host-card-title' }, `MTR → ${target}`),
      ),
      tbl,
    );
  },

  http(r) {
    const status = r.ok ? (r.time_ms < 500 ? 'OK' : r.time_ms < 2000 ? 'SLOW' : 'WARN') : 'FAIL';
    const grid = el('div', { class: 'host-card-grid' });
    grid.appendChild(kv('Status', r.status || (r.error || '—')));
    grid.appendChild(kv('Time', ms(r.time_ms)));
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' },
        el('div', { class: 'host-card-title' },
          el('span', { class: `dot ${status.toLowerCase()}` }),
          r.url,
        ),
        badge(status),
      ),
      grid,
    );
  },

  dns(matrix) {
    const tbl = el('table', { class: 'hop-table' });
    const head = el('tr', {}, el('th', {}, 'Домен'));
    matrix.servers.forEach(s => head.appendChild(el('th', {}, s)));
    tbl.appendChild(el('thead', {}, head));
    const tbody = el('tbody');
    matrix.domains.forEach(d => {
      const row = el('tr', {}, el('td', {}, d));
      const sysIp = matrix.results[d]['Системный'] || matrix.results[d]['System'];
      matrix.servers.forEach(s => {
        const val = matrix.results[d][s] || '—';
        const diff = sysIp && val !== sysIp && val !== '—' && val !== 'FAIL' && !sameSubnet(sysIp, val);
        row.appendChild(el('td', { class: 'ip' + (diff ? ' muted' : '') }, val));
      });
      tbody.appendChild(row);
    });
    tbl.appendChild(tbody);
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' }, 'DNS Matrix')),
      tbl,
    );
  },

  external_ip(d) {
    const grid = el('div', { class: 'host-card-grid' });
    const geo = d.geo || {};
    if (geo.ip)       grid.appendChild(kv('IP', geo.ip));
    if (geo.hostname) grid.appendChild(kv('Hostname', geo.hostname));
    if (geo.city)     grid.appendChild(kv('Город', `${geo.city}, ${geo.region || ''}`.trim().replace(/,$/, '')));
    if (geo.country)  grid.appendChild(kv('Страна', geo.country));
    if (geo.org)      grid.appendChild(kv('Провайдер', geo.org));
    if (geo.timezone) grid.appendChild(kv('Timezone', geo.timezone));
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' }, 'Внешний IP')),
      grid,
    );
  },

  sysinfo(info) {
    const grid = el('div', { class: 'host-card-grid' });
    [
      ['Hostname', info.hostname],
      ['ОС', `${info.os || ''}`],
      ['Дистрибутив', info.distrib],
      ['Архитектура', info.arch],
      ['Python', info.python],
      ['Uptime', info.uptime],
      ['Пользователь', info.user],
    ].forEach(([k, v]) => { if (v) grid.appendChild(kv(k, v)); });
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' }, 'Система')),
      grid,
    );
  },

  interfaces(ifaces) {
    const wrap = el('div', {});
    ifaces.forEach(i => {
      const up = i.up !== false;
      const grid = el('div', { class: 'host-card-grid' });
      if (i.mac)   grid.appendChild(kv('MAC', i.mac));
      if (i.mtu)   grid.appendChild(kv('MTU', String(i.mtu)));
      grid.appendChild(kv('Адреса', (i.addresses || []).map(a => `${a.addr}/${a.prefix}`).join(', ') || '—'));
      if (i.dns && i.dns.length) grid.appendChild(kv('DNS', i.dns.join(', ')));

      wrap.appendChild(el('div', { class: 'host-card' },
        el('div', { class: 'host-card-head' },
          el('div', { class: 'host-card-title' },
            el('span', { class: 'dot ' + (up ? 'ok' : 'idle') }),
            i.name,
          ),
          el('span', { class: 'muted xs' }, (i.flags || []).join(', ')),
        ),
        grid,
      ));
    });
    return wrap;
  },

  connections(conns) {
    const tbl = el('table', { class: 'hop-table' });
    tbl.appendChild(el('thead', {}, el('tr', {},
      el('th', {}, 'Proto'),
      el('th', {}, 'State'),
      el('th', {}, 'Local'),
      el('th', {}, 'Remote'),
    )));
    const tbody = el('tbody');
    conns.slice(0, 200).forEach(c => {
      tbody.appendChild(el('tr', {},
        el('td', {}, c.proto),
        el('td', { class: 'muted xs' }, c.state),
        el('td', { class: 'ip' }, c.local),
        el('td', { class: 'ip' }, c.remote),
      ));
    });
    tbl.appendChild(tbody);
    return el('div', { class: 'host-card' },
      el('div', { class: 'host-card-head' }, el('div', { class: 'host-card-title' },
        `Соединения (${conns.length})`)),
      tbl,
    );
  },
};

// ── helpers ─────────────────────────────────────────────────────────────────────

function ms(v) { return v == null ? '—' : `${(+v).toFixed ? v.toFixed(0) : v}ms`; }
function pct(v) { return v == null ? '—' : `${v}%`; }

function kv(k, v) {
  return el('div', {}, el('div', { class: 'k' }, k), el('div', { class: 'v' }, String(v ?? '—')));
}

function statusFromPing(p) {
  const loss = p.loss || 0, avg = p.avg || 0;
  if (loss >= 50 || p.recv === 0) return 'FAIL';
  if (loss >= 10 || avg > 300) return 'WARN';
  if (loss >= 2  || avg > 150) return 'SLOW';
  return 'OK';
}

function badge(status) {
  return el('span', { class: `badge ${status.toLowerCase()}` }, status);
}

function sameSubnet(a, b, prefix = 16) {
  if (!a || !b) return false;
  const pa = a.split('.').slice(0, prefix / 8);
  const pb = b.split('.').slice(0, prefix / 8);
  return pa.join('.') === pb.join('.');
}

function drawSpark(canvas, values) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const W = canvas.width = canvas.parentNode.clientWidth;
  const H = canvas.height = 40;
  ctx.clearRect(0, 0, W, H);
  if (!values.length) return;
  const max = Math.max(...values, 1);
  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#7c9eff';
  ctx.strokeStyle = accent;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * W;
    const y = H - (v / max) * (H - 4) - 2;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}
