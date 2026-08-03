/* EAD ETA — official USCIS data only.
 *
 * No build step, no dependencies, no network calls beyond the two local JSON
 * files. Charts are hand-rolled SVG so the page stays self-contained.
 *
 * A deliberate omission: this file computes no percentiles. USCIS publishes
 * aggregate counts, not per-case durations, and inventing a distribution from
 * a median and a backlog figure would look authoritative while being made up.
 */

'use strict';

const $ = (sel) => document.querySelector(sel);
const MONTH = 30.44;

const state = { official: null, input: { receipt: '', category: '', premium: false } };

/* ------------------------------------------------------------- utilities */

function el(tag, attrs = {}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function makeSvg(host, w, h) {
  host.innerHTML = '';
  const svg = el('svg', {
    viewBox: `0 0 ${w} ${h}`, width: '100%', height: h,
    preserveAspectRatio: 'xMinYMin meet', role: 'img',
  });
  host.appendChild(svg);
  return svg;
}

/** Width of `text` as it will actually render, in viewBox units.
 *
 * Estimating from character count gets proportional fonts wrong by enough to
 * clip a word, so this measures for real: append off-canvas, read, remove.
 */
function measureText(svg, text, cls) {
  const node = el('text', { class: cls, x: -9999, y: -9999 });
  node.textContent = text;
  svg.appendChild(node);
  const w = node.getBBox().width;
  node.remove();
  return w;
}

/** Left margin wide enough for the longest right-aligned label, plus a gutter. */
function leftMarginFor(svg, labels, gutter = 14) {
  const widest = Math.max(0, ...labels.map(([text, cls]) => measureText(svg, text, cls)));
  return Math.ceil(widest) + gutter;
}

function niceTicks(lo, hi, count) {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag * 10;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) {
    out.push(+t.toFixed(6));
  }
  return out;
}

const fmtInt = (n) => n.toLocaleString('en-US');

function fmtDate(d) {
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function addDays(date, days) {
  const out = new Date(date.getTime());
  out.setDate(out.getDate() + days);
  return out;
}

/** Add N business days, skipping weekends.
 *
 * Federal holidays are NOT excluded — there are 11 of them and which ones fall
 * inside a given window depends on the filing date, so a real answer needs a
 * holiday calendar. The result is therefore slightly optimistic and the UI
 * says so rather than presenting it as exact.
 */
function addBusinessDays(date, n) {
  const out = new Date(date.getTime());
  let left = n;
  while (left > 0) {
    out.setDate(out.getDate() + 1);
    const day = out.getDay();
    if (day !== 0 && day !== 6) left--;
  }
  return out;
}

function businessDaysBetween(from, to) {
  if (to <= from) return 0;
  let count = 0;
  const cur = new Date(from.getTime());
  while (cur < to) {
    cur.setDate(cur.getDate() + 1);
    const day = cur.getDay();
    if (day !== 0 && day !== 6) count++;
  }
  return count;
}

function parseISO(s) {
  if (!s) return null;
  const [y, m, d] = s.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return Number.isFinite(dt.getTime()) ? dt : null;
}

/* --------------------------------------------------------------- tooltip */

const tip = {
  node: null,
  show(html, x, y) {
    if (!this.node) this.node = $('#tooltip');
    this.node.innerHTML = html;
    this.node.hidden = false;
    const pad = 12;
    const r = this.node.getBoundingClientRect();
    let left = x + pad;
    if (left + r.width > window.innerWidth - 8) left = x - r.width - pad;
    this.node.style.left = `${Math.max(8, left)}px`;
    this.node.style.top = `${y - r.height - pad}px`;
  },
  hide() { if (this.node) this.node.hidden = true; },
};

function hoverable(node, html) {
  node.style.cursor = 'default';
  node.addEventListener('mousemove', (e) => tip.show(html, e.clientX, e.clientY));
  node.addEventListener('mouseleave', () => tip.hide());
}

/* ---------------------------------------------------------------- lookup */

function bucketFor(categoryId) {
  const buckets = state.official?.buckets || [];
  if (!buckets.length) return null;
  if (categoryId) {
    const hit = buckets.find((b) => (b.categories || []).includes(categoryId));
    if (hit) return hit;
  }
  // Nothing selected: the catch-all bucket is the most broadly relevant.
  return buckets.reduce((a, b) => (b.pending > a.pending ? b : a));
}

function historyFor(bucketKey) {
  return (state.official?.history?.series || []).find((s) => s.bucket === bucketKey) || null;
}

/* ------------------------------------------------------------ hero tiles */

function tile(label, value, note, tone) {
  return `<div class="tile${tone ? ` ${tone}` : ''}">
    <div class="k">${label}</div>
    <div class="v">${value}</div>
    <div class="s">${note}</div>
  </div>`;
}

function renderHero(bucket, receipt, futureDate) {
  const card = $('#hero');
  if (!bucket || (!receipt && !futureDate)) { card.hidden = true; return; }
  card.hidden = false;

  // A receipt date can't be in the future. Say so plainly rather than rendering
  // a negative wait, which is what an unguarded subtraction produces.
  if (futureDate) {
    $('#hero-sub').textContent = '';
    $('#hero-tiles').innerHTML = '';
    $('#hero-note').innerHTML = `<strong>That receipt date is in the future.</strong>
      Enter the date on your I-797C receipt notice — the day USCIS took your
      filing in, not a date you expect something to happen.`;
    return;
  }

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const elapsedDays = Math.round((today - receipt) / 86400000);
  const elapsedMo = elapsedDays / MONTH;

  const pub = bucket.published_months;
  const imp = bucket.implied_months;

  const pubDate = pub != null ? addDays(receipt, Math.round(pub * MONTH)) : null;
  const impDate = imp != null ? addDays(receipt, Math.round(imp * MONTH)) : null;

  const pubNote = pubDate
    ? (pubDate <= today
      ? `${fmtDate(pubDate)} — already passed`
      : `around ${fmtDate(pubDate)}`)
    : 'not published';

  const impNote = impDate
    ? (impDate <= today
      ? `${fmtDate(impDate)} — already passed`
      : `around ${fmtDate(impDate)}`)
    : 'not derivable';

  const past = bucket.share_past_target;

  // Premium filers are on a completely different clock, and the one thing they
  // need to know is whether USCIS has blown the guarantee — because that
  // triggers a fee refund. Lead with that rather than with queue statistics.
  const p = state.official?.premium;
  if (state.input.premium && p) {
    const deadline = addBusinessDays(receipt, p.business_days);
    const lapsed = deadline < today;
    const bdElapsed = businessDaysBetween(receipt, today);

    $('#hero-sub').textContent =
      `Filed ${fmtDate(receipt)} with premium processing · ${p.business_days}-business-day guarantee`;

    $('#hero-tiles').innerHTML = [
      tile('Waiting so far', `${fmtInt(elapsedDays)} days`,
        `${fmtInt(bdElapsed)} business days`),
      tile(`${p.business_days}-business-day deadline`, fmtDate(deadline),
        lapsed ? 'already passed' : `in ${fmtInt(businessDaysBetween(today, deadline))} business days`,
        lapsed ? 'warn' : ''),
      tile('Standard median for comparison', pub != null ? `${pub.toFixed(1)} mo` : '—',
        'what you would face without premium'),
      tile('Fee refund', lapsed ? 'Possibly owed' : 'Not yet',
        lapsed ? 'if no action was taken' : 'guarantee still running',
        lapsed ? 'warn' : ''),
    ].join('');

    $('#hero-note').innerHTML = lapsed
      ? `<strong>USCIS's deadline has passed.</strong> If it took no adjudicative
         action on your case by ${fmtDate(deadline)}, it owes you a refund of the
         premium processing fee — the case still gets processed. Note that an RFE
         <em>counts</em> as action and restarts a fresh ${p.business_days}-day
         period, so check whether one was issued before assuming a refund is due.
         This date excludes federal holidays, so treat it as slightly early.`
      : `Your guarantee runs to ${fmtDate(deadline)}. If USCIS takes no
         adjudicative action by then it must refund the premium fee. Bear in mind
         the guarantee covers a <em>decision or an RFE</em>, not an approval, and
         this date doesn't subtract federal holidays.`;
    return;
  }

  $('#hero-sub').textContent =
    `Filed ${fmtDate(receipt)} · USCIS reports this under "${shortBucket(bucket.bucket)}"`;

  $('#hero-tiles').innerHTML = [
    tile('Waiting so far', `${fmtInt(elapsedDays)} days`,
      `${elapsedMo.toFixed(1)} months`),
    tile('USCIS published median', pub != null ? `${pub.toFixed(1)} mo` : '—', pubNote,
      pubDate && pubDate <= today ? 'warn' : ''),
    tile('Backlog-implied wait', imp != null ? `${imp.toFixed(1)} mo` : '—', impNote,
      impDate && impDate <= today ? 'warn' : ''),
    tile('Pending cases past target', past != null ? `${Math.round(past * 100)}%` : '—',
      `of ${fmtInt(bucket.pending)} pending`,
      past != null && past > 0.5 ? 'warn' : ''),
  ].join('');

  let note;
  if (pub != null && elapsedMo > pub && imp != null && elapsedMo < imp) {
    note = `You are past the published median but still inside the backlog-implied
      window. That combination is normal right now: for this bucket USCIS reports
      ${past != null ? `${Math.round(past * 100)}% of` : 'much of'} the pending
      queue as already past target, which means the published median describes
      cases that finished, not the queue you're in.`;
  } else if (imp != null && elapsedMo > imp) {
    note = `You are past both the published median and the backlog-implied wait.
      At this point the aggregate data has little left to say about your case —
      a case inquiry or an attorney is a more useful next step than a projection.`;
  } else if (pub != null && elapsedMo < pub) {
    note = `You are still inside the published median. Nothing here suggests your
      case is unusual yet.`;
  } else {
    note = '';
  }
  $('#hero-note').innerHTML = note;
}

/* ------------------------------------------------------- reality check */

function drawReality(bucket, receipt) {
  const card = $('#reality');
  if (!bucket) { card.hidden = true; return; }
  card.hidden = false;

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const elapsedMo = receipt ? (today - receipt) / 86400000 / MONTH : null;

  const rows = [
    { key: 'USCIS published', v: bucket.published_months, color: 'var(--series-2)',
      note: 'median of completed cases' },
    { key: 'Backlog-implied', v: bucket.implied_months, color: 'var(--series-3)',
      note: 'pending ÷ throughput' },
  ];

  const p = state.official?.premium;
  if (state.input.premium && p && receipt) {
    const deadline = addBusinessDays(receipt, p.business_days);
    rows.unshift({
      key: 'Premium guarantee',
      v: +((deadline - receipt) / 86400000 / MONTH).toFixed(1),
      color: 'var(--series-4)',
      note: `${p.business_days} business days`,
    });
  }

  if (elapsedMo != null) {
    rows.push({ key: 'You, so far', v: +elapsedMo.toFixed(1), color: 'var(--series-1)',
      note: 'days since receipt' });
  }
  const live = rows.filter((r) => r.v != null);

  const host = $('#chart-reality');
  const W = 760, rowH = 52;
  const M = { top: 12, right: 104, bottom: 34, left: 136 };
  const H = M.top + live.length * rowH + M.bottom;
  const svg = makeSvg(host, W, H);

  // "median of completed cases" is wider than the row names above it, so size
  // the margin to whichever label is actually longest rather than guessing.
  M.left = Math.max(M.left, leftMarginFor(svg, [
    ...live.map((r) => [r.key, 'row-label']),
    ...live.map((r) => [r.note, 'tick']),
  ]));
  const iw = W - M.left - M.right;

  const maxV = Math.max(...live.map((r) => r.v)) * 1.12;
  const x = (v) => (v / maxV) * iw;
  const bh = 22;
  const plotBottom = M.top + live.length * rowH - 16;

  for (const t of niceTicks(0, maxV, 5)) {
    if (t > maxV) continue;
    svg.appendChild(el('line', {
      class: 'grid-line', x1: M.left + x(t), x2: M.left + x(t), y1: M.top, y2: plotBottom,
    }));
    const lab = el('text', { class: 'tick', x: M.left + x(t), y: plotBottom + 16, 'text-anchor': 'middle' });
    lab.textContent = t;
    svg.appendChild(lab);
  }

  live.forEach((r, i) => {
    const y = M.top + i * rowH + 4;

    const name = el('text', { class: 'row-label', x: M.left - 12, y: y + bh / 2 + 4, 'text-anchor': 'end' });
    name.textContent = r.key;
    svg.appendChild(name);

    const sub = el('text', { class: 'tick', x: M.left - 12, y: y + bh / 2 + 19, 'text-anchor': 'end' });
    sub.textContent = r.note;
    svg.appendChild(sub);

    const bar = el('rect', { x: M.left, y, width: Math.max(2, x(r.v)), height: bh, rx: 4, fill: r.color });
    hoverable(bar, `<strong>${r.key}</strong><br>${r.v.toFixed(1)} months<br>
      <span class="t-muted">${r.note}</span>`);
    svg.appendChild(bar);

    // Direct label on every bar — the relief required for sub-3:1 fills on light.
    const val = el('text', { class: 'bar-label', x: M.left + x(r.v) + 8, y: y + bh / 2 + 4 });
    val.textContent = `${r.v.toFixed(1)} mo`;
    svg.appendChild(val);
  });

  const xt = el('text', { class: 'axis-title', x: M.left + iw / 2, y: H - 4, 'text-anchor': 'middle' });
  xt.textContent = 'Months';
  svg.appendChild(xt);

  $('#legend-reality').innerHTML = live.map((r) =>
    `<span class="item"><span class="swatch" style="background:${r.color}"></span>${r.key}</span>`).join('');

  renderVerdict(bucket);
}

function renderVerdict(bucket) {
  const pub = bucket.published_months;
  const imp = bucket.implied_months;
  const past = bucket.share_past_target;
  const ratio = bucket.inflow_ratio;

  if (pub == null || imp == null) { $('#reality-verdict').textContent = ''; return; }

  const factor = imp / pub;
  let lead;
  if (factor >= 2) {
    lead = `The backlog implies a wait <strong>${factor.toFixed(1)}× longer</strong>
      than the published median.`;
  } else if (factor >= 1.2) {
    lead = `The backlog implies a somewhat longer wait than the published median
      (${factor.toFixed(1)}×).`;
  } else {
    lead = `The two readings broadly agree for this bucket.`;
  }

  // Little's Law is only trustworthy near steady state, so say which regime
  // this bucket is actually in rather than presenting one number as settled.
  let flow = '';
  if (ratio != null) {
    if (ratio > 1.25) {
      flow = ` Filings are arriving <strong>${ratio.toFixed(2)}× faster than they're
        completed</strong>, so this queue is still growing and the implied wait is
        likely to get worse, not better.`;
    } else if (ratio < 0.85) {
      flow = ` Completions are outpacing filings (${ratio.toFixed(2)}× inflow), so
        this queue is shrinking and the implied wait overstates what a new filer
        should expect.`;
    } else {
      flow = ` Filings and completions are near balance (${ratio.toFixed(2)}× inflow),
        which is the regime where this backlog estimate is most trustworthy.`;
    }
  }

  const backlog = past != null && past > 0
    ? ` USCIS's own backlog report puts <strong>${Math.round(past * 100)}% of the
        ${fmtInt(bucket.pending)} pending cases past its target</strong>.`
    : ` USCIS reports no net backlog here — the queue is inside its own target.`;

  $('#reality-verdict').innerHTML = lead + flow + backlog;
}

/* ---------------------------------------------------- premium processing */

function categoryMeta(id) {
  return (state.official?.categories || []).find((c) => c.id === id) || null;
}

function backlogRow(key) {
  return (state.official?.backlog_detail || []).find((b) => b.bucket === key) || null;
}

function drawPremium(bucket, receipt) {
  const card = $('#premium');
  const p = state.official?.premium;
  if (!p) { card.hidden = true; return; }

  const meta = categoryMeta(state.input.category);
  const eligible = !!meta?.premium_eligible;

  // Only surface this where it's actionable, or where the user has picked
  // nothing yet and might not know it exists.
  if (state.input.category && !eligible) { card.hidden = true; return; }
  card.hidden = false;

  const premiumBacklog = backlogRow('premium processed');
  const yourBacklog = bucket ? backlogRow(bucket.bucket) : null;

  $('#premium-sub').innerHTML = eligible
    ? `Your category is eligible. USCIS guarantees adjudicative action within
       <strong>${p.business_days} business days</strong> or refunds the fee.`
    : `Available for ${p.eligible_label}. Select one of those categories to see
       how it compares to your queue.`;

  const tiles = [
    tile('Guaranteed window', `${p.business_days} business days`,
      `about ${p.approx_calendar_days} calendar days`),
  ];

  if (bucket?.published_months != null) {
    const mult = (bucket.published_months * MONTH) / p.approx_calendar_days;
    tiles.push(tile('vs. your queue', `${mult.toFixed(1)}× faster`,
      `standard published median is ${bucket.published_months.toFixed(1)} mo`));
  }
  if (premiumBacklog) {
    tiles.push(tile('Premium cases past target', fmtInt(premiumBacklog.net_backlog),
      yourBacklog?.net_backlog
        ? `vs ${fmtInt(yourBacklog.net_backlog)} in your bucket`
        : 'across all premium I-765 filings'));
  }
  $('#premium-tiles').innerHTML = tiles.join('');

  let note = '';
  if (premiumBacklog && yourBacklog?.net_backlog) {
    note = `USCIS's own backlog report lists <strong>${fmtInt(premiumBacklog.net_backlog)}</strong>
      premium-processed I-765 cases past target, against
      <strong>${fmtInt(yourBacklog.net_backlog)}</strong> in your bucket. On the
      agency's own numbers the guarantee is being met at scale.`;
  }
  if (eligible && receipt) {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const elapsed = Math.round((today - receipt) / 86400000);
    note += elapsed > p.approx_calendar_days
      ? ` You are already ${fmtInt(elapsed)} days in, so upgrading now would start a
         fresh ${p.business_days}-business-day clock from the date USCIS receives
         Form I-907 — not from your original receipt date.`
      : ` You can upgrade a pending case at any point; the clock starts when USCIS
         receives Form I-907.`;
  }
  $('#premium-note').innerHTML = note;

  $('#premium-caveats').innerHTML = p.caveats.map((c) => `<li>${c}</li>`).join('');
  $('#premium-links').innerHTML =
    `<a href="${p.links.source}">USCIS premium processing rules</a> ·
     <a href="${p.links.fee_schedule}">current fee schedule</a> ·
     <a href="${p.links.form}">Form I-907</a>.
     The fee changed in 2026 and USCIS publishes it only on the fee schedule, so
     it isn't reproduced here — check the link before filing.`;
}

/* ---------------------------------------------------------------- trend */

const TREND_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];

function drawTrend(bucketKey) {
  const hist = state.official?.history;
  const card = $('#trend');
  if (!hist?.series?.length) { card.hidden = true; return; }
  card.hidden = false;

  const years = hist.fiscal_years;
  const series = hist.series;
  const host = $('#chart-trend');

  const W = 780, H = 340;
  const M = { top: 16, right: 168, bottom: 44, left: 48 };
  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const svg = makeSvg(host, W, H);

  const maxY = Math.max(...series.flatMap((s) => s.months)) * 1.12;
  const x = (i) => M.left + (i / (years.length - 1)) * iw;
  const y = (v) => M.top + ih - (v / maxY) * ih;

  for (const t of niceTicks(0, maxY, 5)) {
    svg.appendChild(el('line', { class: 'grid-line', x1: M.left, x2: M.left + iw, y1: y(t), y2: y(t) }));
    const lab = el('text', { class: 'tick', x: M.left - 8, y: y(t) + 4, 'text-anchor': 'end' });
    lab.textContent = t;
    svg.appendChild(lab);
  }

  years.forEach((yr, i) => {
    const lab = el('text', { class: 'tick', x: x(i), y: M.top + ih + 18, 'text-anchor': 'middle' });
    lab.textContent = `'${String(yr).slice(2)}`;
    svg.appendChild(lab);
  });

  svg.appendChild(el('line', { class: 'axis-line', x1: M.left, x2: M.left + iw, y1: y(0), y2: y(0) }));

  const partial = new Set(hist.partial_years || []);
  const firstPartial = years.findIndex((yr) => partial.has(yr));
  const endLabels = [];

  series.forEach((s, si) => {
    const color = TREND_COLORS[si % TREND_COLORS.length];
    const active = s.bucket === bucketKey;
    const solidPts = [];
    const dashPts = [];

    s.months.forEach((v, i) => {
      const pt = [x(i), y(v)];
      if (firstPartial >= 0 && i >= firstPartial - 1) dashPts.push(pt);
      if (firstPartial < 0 || i <= firstPartial - 1) solidPts.push(pt);
    });

    const path = (pts, dashed) => {
      if (pts.length < 2) return;
      svg.appendChild(el('path', {
        d: pts.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' '),
        fill: 'none', stroke: color,
        'stroke-width': active ? 3 : 2,
        'stroke-opacity': active || !bucketKey ? 1 : 0.42,
        'stroke-dasharray': dashed ? '4 3' : 'none',
        'stroke-linejoin': 'round', 'stroke-linecap': 'round',
      }));
    };
    path(solidPts, false);
    path(dashPts, true);

    s.months.forEach((v, i) => {
      const dot = el('circle', {
        cx: x(i), cy: y(v), r: active ? 4.5 : 3.5, fill: color,
        stroke: 'var(--surface-1)', 'stroke-width': 2,
        'fill-opacity': active || !bucketKey ? 1 : 0.42,
      });
      hoverable(dot, `<strong>${s.label}</strong><br>FY${years[i]}: ${v} months${
        partial.has(years[i]) ? '<br><span class="t-muted">partial year</span>' : ''}`);
      svg.appendChild(dot);
    });

    endLabels.push({
      y: y(s.months[s.months.length - 1]),
      text: shortLabel(s.label), color, active,
    });
  });

  placeEndLabels(svg, endLabels, M.left + iw, M.top, M.top + ih, bucketKey);

  const yt = el('text', { class: 'axis-title', x: 12, y: M.top + ih / 2,
    'text-anchor': 'middle', transform: `rotate(-90 12 ${M.top + ih / 2})` });
  yt.textContent = 'Median months';
  svg.appendChild(yt);

  const xt = el('text', { class: 'axis-title', x: M.left + iw / 2, y: H - 6, 'text-anchor': 'middle' });
  xt.textContent = 'Fiscal year';
  svg.appendChild(xt);

  $('#legend-trend').innerHTML = series.map((s, i) =>
    `<span class="item"><span class="swatch" style="background:${TREND_COLORS[i % 4]}"></span>${shortLabel(s.label)}</span>`).join('');

  const active = series.find((s) => s.bucket === bucketKey);
  const notes = hist.notes || [];
  $('#trend-note').innerHTML = (active
    ? `Your basis of filing is <strong>${shortLabel(active.label)}</strong>, shown
       in bold: ${active.change_pct >= 0 ? 'up' : 'down'}
       <strong>${Math.abs(active.change_pct)}%</strong> across the window. `
    : '') + `Dashed segments are FY2024, which USCIS reports for October 2023–January
       2024 only. ${notes.find((n) => n.includes('methodology')) || ''}`;
}

/** Direct end-labels, nudged apart so close-finishing lines stay readable.
 *
 * Series ending within a few months of each other collide at 11.5px type
 * (Parole and Asylum finish 0.3 months apart), so labels are spread to a
 * minimum gap and a leader line is drawn wherever one had to move.
 */
function placeEndLabels(svg, labels, xAnchor, top, bottom, bucketKey) {
  const GAP = 14;
  const sorted = [...labels].sort((a, b) => a.y - b.y);

  // Push down through the stack, then clamp back up if it overruns the plot.
  sorted.forEach((l, i) => {
    l.ly = i === 0 ? l.y : Math.max(l.y, sorted[i - 1].ly + GAP);
  });
  const overflow = sorted[sorted.length - 1].ly - bottom;
  if (overflow > 0) {
    for (let i = sorted.length - 1; i >= 0; i--) {
      sorted[i].ly = Math.min(sorted[i].ly, (i === sorted.length - 1 ? bottom : sorted[i + 1].ly - GAP));
    }
  }
  sorted.forEach((l) => { l.ly = Math.max(top + 6, l.ly); });

  for (const l of sorted) {
    const dim = !(l.active || !bucketKey);
    if (Math.abs(l.ly - l.y) > 1.5) {
      svg.appendChild(el('path', {
        d: `M${xAnchor + 2},${l.y} L${xAnchor + 7},${l.ly}`,
        stroke: l.color, 'stroke-width': 1, fill: 'none',
        'stroke-opacity': dim ? 0.4 : 0.8,
      }));
    }
    const node = el('text', {
      class: 'series-label', x: xAnchor + 10, y: l.ly + 4, fill: l.color,
      'font-weight': l.active ? 700 : 500,
      'fill-opacity': dim ? 0.5 : 1,
    });
    node.textContent = l.text;
    svg.appendChild(node);
  }
}

function shortLabel(label) {
  return label
    .replace('Based on a pending ', '')
    .replace('Based on ', '')
    .replace('All other applications for employment authorization', 'All other')
    .replace('asylum application', 'Asylum pending')
    .replace('I-485 adjustment application', 'I-485 pending')
    .replace(/^parole$/, 'Parole');
}

/* ---------------------------------------------------------------- queue */

function drawQueue(bucket) {
  const card = $('#queue');
  const buckets = state.official?.buckets || [];
  if (!buckets.length) { card.hidden = true; return; }
  card.hidden = false;

  const host = $('#chart-queue');
  const W = 780, rowH = 46;
  const M = { top: 28, right: 130, bottom: 34, left: 150 };
  const H = M.top + buckets.length * rowH + M.bottom;
  const svg = makeSvg(host, W, H);

  M.left = Math.max(M.left,
    leftMarginFor(svg, buckets.map((b) => [shortBucket(b.bucket), 'row-label'])));
  const iw = W - M.left - M.right;

  const maxP = Math.max(...buckets.map((b) => b.pending)) * 1.08;
  const x = (v) => (v / maxP) * iw;
  const bh = 20;

  for (const t of niceTicks(0, maxP, 4)) {
    svg.appendChild(el('line', {
      class: 'grid-line', x1: M.left + x(t), x2: M.left + x(t),
      y1: M.top - 8, y2: M.top + buckets.length * rowH - 14,
    }));
    const lab = el('text', {
      class: 'tick', x: M.left + x(t), y: M.top + buckets.length * rowH + 4, 'text-anchor': 'middle',
    });
    lab.textContent = t >= 1000 ? `${Math.round(t / 1000)}k` : t;
    svg.appendChild(lab);
  }

  const head = el('text', { class: 'tick', x: M.left, y: M.top - 14 });
  head.textContent = 'Pending cases — filled portion is past USCIS\'s target';
  svg.appendChild(head);

  buckets.forEach((b, i) => {
    const y = M.top + i * rowH;
    const isYou = bucket && b.bucket === bucket.bucket;

    const name = el('text', { class: 'row-label', x: M.left - 12, y: y + bh / 2 + 4, 'text-anchor': 'end' });
    name.textContent = shortBucket(b.bucket);
    if (isYou) name.setAttribute('font-weight', '700');
    svg.appendChild(name);

    // Total pending, recessive.
    const total = el('rect', {
      x: M.left, y, width: Math.max(2, x(b.pending)), height: bh, rx: 4,
      fill: 'var(--series-1)', 'fill-opacity': isYou ? 0.28 : 0.16,
    });
    hoverable(total, `<strong>${shortBucket(b.bucket)}</strong><br>
      ${fmtInt(b.pending)} pending<br>${fmtInt(b.net_backlog ?? 0)} past target`);
    svg.appendChild(total);

    // Past-target portion, emphatic. 2px surface gap keeps the two readable.
    if (b.net_backlog) {
      const w = Math.max(2, x(b.net_backlog));
      svg.appendChild(el('rect', {
        x: M.left, y: y + 2, width: w, height: bh - 4, rx: 3,
        fill: 'var(--series-1)', 'fill-opacity': isYou ? 1 : 0.75,
      }));
    }

    const pct = b.share_past_target;
    const val = el('text', { class: 'bar-label', x: M.left + x(b.pending) + 8, y: y + bh / 2 + 4 });
    val.textContent = pct != null ? `${Math.round(pct * 100)}% past` : `${fmtInt(b.pending)}`;
    svg.appendChild(val);
  });

  const xt = el('text', { class: 'axis-title', x: M.left + iw / 2, y: H - 4, 'text-anchor': 'middle' });
  xt.textContent = 'Pending cases';
  svg.appendChild(xt);

  const worst = buckets.reduce((a, b) =>
    ((b.share_past_target ?? 0) > (a.share_past_target ?? 0) ? b : a));
  $('#queue-note').innerHTML = worst.share_past_target
    ? `The deepest backlog is <strong>${shortBucket(worst.bucket)}</strong>, with
       ${Math.round(worst.share_past_target * 100)}% of ${fmtInt(worst.pending)}
       pending cases already past USCIS's own target.`
    : '';
}

function shortBucket(key) {
  return ({
    'asylum': 'Asylum pending',
    'adjustment of status': 'I-485 pending',
    'daca': 'DACA',
    'parolees': 'Parole',
    'all other': 'All other',
    'premium processed': 'Premium',
  })[key] || key;
}

/* ---------------------------------------------------------------- table */

function renderTable(bucket) {
  const o = state.official;
  if (!o?.buckets?.length) return;
  $('#table-card').hidden = false;

  const rows = o.buckets.map((b) => `<tr${bucket && b.bucket === bucket.bucket ? ' class="you"' : ''}>
    <td>${shortBucket(b.bucket)}</td>
    <td>${fmtInt(b.pending)}</td>
    <td>${fmtInt(b.completions)}</td>
    <td>${b.published_months != null ? b.published_months.toFixed(1) : '—'}</td>
    <td>${b.implied_months != null ? b.implied_months.toFixed(1) : '—'}</td>
    <td>${b.share_past_target != null ? `${Math.round(b.share_past_target * 100)}%` : '—'}</td>
  </tr>`).join('');

  const hist = o.history;
  const histRows = (hist?.series || []).map((s) => `<tr>
    <td>${shortLabel(s.label)}</td>
    ${s.months.map((m) => `<td>${m}</td>`).join('')}
  </tr>`).join('');

  $('#data-table').innerHTML = `
    <caption>Quarterly volumes — ${o.period || 'latest'}</caption>
    <thead><tr>
      <th>Bucket</th><th>Pending</th><th>Completed</th>
      <th>Published mo</th><th>Implied mo</th><th>Past target</th>
    </tr></thead>
    <tbody>${rows}</tbody>
    ${hist ? `<caption class="mid">Historical median months by fiscal year</caption>
    <thead><tr><th>Basis of filing</th>${hist.fiscal_years.map((y) =>
      `<th>FY${String(y).slice(2)}</th>`).join('')}</tr></thead>
    <tbody>${histRows}</tbody>` : ''}`;
}

/** Enable the premium control only where USCIS actually allows it.
 *
 * Silently ignoring the selection for an ineligible category would be worse
 * than disabling it — someone could conclude they're on a 30-day clock when no
 * such option exists for their category.
 */
function syncPremiumControl() {
  const sel = $('#in-premium');
  const note = $('#premium-note-input');
  const p = state.official?.premium;
  const meta = categoryMeta(state.input.category);

  if (!p) { sel.disabled = true; note.textContent = ''; return; }

  if (!state.input.category) {
    sel.disabled = true;
    sel.value = '';
    note.textContent = 'Pick a category first — only F-1 OPT categories qualify.';
    return;
  }

  if (!meta?.premium_eligible) {
    sel.disabled = true;
    sel.value = '';
    note.textContent = `Not available for this category. On Form I-765, USCIS `
      + `allows premium processing for ${p.eligible_label}.`;
    return;
  }

  sel.disabled = false;
  sel.value = state.input.premium ? '1' : '';
  note.textContent = state.input.premium
    ? `${p.business_days} business days, or USCIS refunds the fee.`
    : 'Eligible — select if you filed or upgraded with Form I-907.';
}

/* --------------------------------------------------------------- render */

function render() {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  let receipt = parseISO(state.input.receipt);
  const futureDate = !!(receipt && receipt > today);
  if (futureDate) receipt = null;   // downstream charts must never see it

  const bucket = bucketFor(state.input.category);

  const noteEl = $('#bucket-note');
  const histKey = categoryMeta(state.input.category)?.history_bucket;
  const ownBacklog = histKey && histKey !== bucket?.bucket ? backlogRow(histKey) : null;

  if (!bucket) {
    noteEl.textContent = '';
  } else if (ownBacklog && !ownBacklog.in_quarterly_report) {
    // e.g. parole: broken out in the backlog report, folded into the four-way
    // split in the quarterly one. Say so rather than implying a clean match.
    noteEl.textContent = `USCIS gives this its own line in the backlog report `
      + `(${fmtInt(ownBacklog.net_backlog)} past target) but folds it into `
      + `"${shortBucket(bucket.bucket)}" for the quarterly figures below.`;
  } else {
    noteEl.textContent = `USCIS reports this under "${shortBucket(bucket.bucket)}".`;
  }

  renderHero(bucket, receipt, futureDate);
  drawReality(bucket, receipt);
  drawPremium(bucket, receipt);
  // The factsheet slices differently from the quarterly report — parole has its
  // own history series but no quarterly row — so the trend uses its own mapping.
  drawTrend(categoryMeta(state.input.category)?.history_bucket
    || (state.input.category ? null : undefined));
  drawQueue(bucket);
  renderTable(bucket);

  syncPremiumControl();

  const params = new URLSearchParams();
  if (state.input.receipt) params.set('r', state.input.receipt);
  if (state.input.category) params.set('c', state.input.category);
  if (state.input.premium) params.set('p', '1');
  history.replaceState(null, '', params.toString() ? `?${params}` : location.pathname);
}

/* ----------------------------------------------------------------- init */

async function init() {
  let official;
  try {
    official = await fetch('data/official.json').then((r) => r.json());
  } catch {
    $('#meta-line').textContent =
      'Could not load data/official.json — run "python -m scraper.build" first.';
    return;
  }
  state.official = official;

  const sel = $('#in-category');
  sel.innerHTML = '<option value="">All I-765 (no category chosen)</option>' +
    (official.categories || []).map((c) =>
      `<option value="${c.id}">${c.label}</option>`).join('');

  const params = new URLSearchParams(location.search);
  state.input.receipt = params.get('r') || '';
  state.input.category = params.get('c') || '';
  // A URL can carry p=1 with an ineligible category; validate rather than trust.
  state.input.premium = params.get('p') === '1'
    && !!(official.categories || []).find(
      (c) => c.id === params.get('c') && c.premium_eligible);

  // Stop the picker offering future dates. render() still guards, because a
  // URL parameter bypasses the input entirely.
  $('#in-receipt').max = new Date().toISOString().slice(0, 10);
  $('#in-receipt').value = state.input.receipt;
  sel.value = state.input.category;

  $('#in-receipt').addEventListener('change', (e) => {
    state.input.receipt = e.target.value; render();
  });
  sel.addEventListener('change', (e) => {
    state.input.category = e.target.value;
    // Switching to an ineligible category must clear a stale premium selection,
    // or the results would keep showing a guarantee that doesn't apply.
    if (!categoryMeta(state.input.category)?.premium_eligible) {
      state.input.premium = false;
    }
    render();
  });
  $('#in-premium').addEventListener('change', (e) => {
    state.input.premium = e.target.value === '1'; render();
  });

  const when = official.generated ? new Date(official.generated) : null;
  $('#meta-line').innerHTML = `Official USCIS data${
    official.period ? `, ${official.period}` : ''}${
    when ? ` · refreshed ${fmtDate(when)}` : ''} · no crowd-sourced data`;

  const urls = official.source_urls || {};
  const hist = official.history?.source || {};
  $('#sources').innerHTML = `<p class="hint">Sources:
    ${urls.forms ? `<a href="${urls.forms}">quarterly form data</a> · ` : ''}
    ${urls.backlog ? `<a href="${urls.backlog}">net backlog report</a> · ` : ''}
    ${hist.factsheet ? `<a href="${hist.factsheet}">historical processing times (FY16–FY24)</a>` : ''}
    </p>`;

  render();
}

init();
