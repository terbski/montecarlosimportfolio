'use strict';

// ── Config ────────────────────────────────────────────────────────────────────
const DATA_URL = 'results/data.json';

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor:  'transparent',
  font:  { color: '#e6edf3', family: 'Inter, Segoe UI, system-ui, sans-serif', size: 11 },
  xaxis: { gridcolor: '#21262d', zerolinecolor: '#30363d' },
  yaxis: { gridcolor: '#21262d', zerolinecolor: '#30363d' },
  margin: { t: 20, b: 40, l: 60, r: 20 },
  legend: { bgcolor: 'transparent', bordercolor: 'transparent' },
};

const PLOTLY_CONFIG = { responsive: true, displayModeBar: false };

// ── Main ──────────────────────────────────────────────────────────────────────
fetch(DATA_URL)
  .then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then(data => {
    renderAll(data);
  })
  .catch(err => {
    document.querySelector('main').innerHTML =
      `<div class="alert">Błąd ładowania danych: ${err.message}.<br>
       Uruchom najpierw: <code>python simulation/run_simulation.py</code></div>`;
  });

// ── Render orchestrator ───────────────────────────────────────────────────────
function renderAll(d) {
  renderHeader(d.meta);
  renderKPIs(d);
  renderExcludedAlert(d.meta);
  renderFanChart(d);
  renderHistogram(d);
  renderMultiHorizon(d.risk_metrics.multi_horizon, d.meta.portfolio_value_usd);
  renderDrawdown(d.simulation.drawdown_histogram);
  renderAllocation(d.assets);
  renderCorrelation(d.correlations);
  renderVolatility(d.assets);
  renderStressTests(d.stress_tests, d.meta.portfolio_value_usd);
  renderAssetsTable(d.assets);
}

// ── Header ────────────────────────────────────────────────────────────────────
function renderHeader(meta) {
  document.getElementById('last-updated').textContent =
    `Ostatnia aktualizacja: ${meta.run_date} | ${meta.n_simulations.toLocaleString()} symulacji × ${meta.simulation_days} dni`;

  const pnlSign = meta.unrealized_pnl_pct >= 0 ? '+' : '';
  const pnlClass = meta.unrealized_pnl_pct >= 0 ? 'positive' : 'negative';

  document.getElementById('header-stats').innerHTML = `
    <div class="stat-item">
      <div class="stat-label">Wartość rynkowa</div>
      <div class="stat-value neutral">$${fmt(meta.portfolio_value_usd)}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">P&L niezrealizowany</div>
      <div class="stat-value ${pnlClass}">${pnlSign}${meta.unrealized_pnl_pct}%</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">GBP/USD</div>
      <div class="stat-value neutral">${meta.gbp_usd}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">EUR/USD</div>
      <div class="stat-value neutral">${meta.eur_usd}</div>
    </div>
  `;
}

// ── Excluded alert ────────────────────────────────────────────────────────────
function renderExcludedAlert(meta) {
  const el = document.getElementById('excluded-alert');
  if (meta.excluded_tickers && meta.excluded_tickers.length > 0) {
    el.textContent =
      `Wykluczone z symulacji (za mało danych): ${meta.excluded_tickers.join(', ')}`;
    el.classList.remove('hidden');
  }
}

// ── KPI Cards ─────────────────────────────────────────────────────────────────
function renderKPIs(d) {
  const rm = d.risk_metrics;
  const probs = rm.probabilities;

  const v0 = d.meta.portfolio_value_usd;
  const varSign = rm.var_95.loss_pct >= 0 ? '-' : '+';  // ujemna strata = zysk
  const var95Class = rm.var_95.loss_pct > 0 ? 'negative' : 'positive';
  const var99Class = rm.var_99.loss_pct > 0 ? 'negative' : 'positive';

  const kpis = [
    {
      label: 'Mediana (1 rok)',
      value: `$${fmt(rm.median_end_usd)}`,
      sub:   pnlStr(rm.median_end_usd, v0),
      cls:   rm.median_end_usd >= v0 ? 'positive' : 'negative',
    },
    {
      label: 'VaR 95%',
      value: rm.var_95.loss_pct > 0
        ? `-$${fmt(rm.var_95.loss_usd)}`
        : `+$${fmt(-rm.var_95.loss_usd)}`,
      sub: rm.var_95.loss_pct > 0
        ? `Maks. strata 95% pewności`
        : `Minimalny zysk 95% pewności`,
      cls: var95Class,
    },
    {
      label: 'VaR 99%',
      value: rm.var_99.loss_pct > 0
        ? `-$${fmt(rm.var_99.loss_usd)}`
        : `+$${fmt(-rm.var_99.loss_usd)}`,
      sub: rm.var_99.loss_pct > 0
        ? `Maks. strata 99% pewności`
        : `Minimalny zysk 99% pewności`,
      cls: var99Class,
    },
    {
      label: 'CVaR 95%',
      value: rm.cvar_95.expected_loss_pct > 0
        ? `-$${fmt(rm.cvar_95.expected_loss_usd)}`
        : `+$${fmt(-rm.cvar_95.expected_loss_usd)}`,
      sub: 'Śr. strata w najgorszych 5%',
      cls: rm.cvar_95.expected_loss_pct > 0 ? 'negative' : 'positive',
    },
    {
      label: 'P(strata)',
      value: `${probs.prob_loss}%`,
      sub: 'Prawdopodob. straty w 1 roku',
      cls: probs.prob_loss > 30 ? 'negative' : probs.prob_loss > 10 ? 'orange' : 'positive',
    },
    {
      label: 'P(zysk > 20%)',
      value: `${probs.prob_gain_20}%`,
      sub: 'Prawdopodob. zysku > 20%',
      cls: probs.prob_gain_20 > 50 ? 'positive' : 'neutral',
    },
    {
      label: 'P(strata > 30%)',
      value: `${probs.prob_loss_30}%`,
      sub: 'Ryzyko dużej straty',
      cls: probs.prob_loss_30 > 10 ? 'negative' : probs.prob_loss_30 > 2 ? 'orange' : 'positive',
    },
    {
      label: 'Aktywa w portfelu',
      value: d.assets.length,
      sub: `${d.meta.history_years} lat historii`,
      cls: 'neutral',
    },
  ];

  document.getElementById('kpi-grid').innerHTML = kpis.map(k => `
    <div class="kpi-card">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value ${k.cls}">${k.value}</div>
      <div class="kpi-sub">${k.sub}</div>
    </div>
  `).join('');
}

// ── Fan Chart ─────────────────────────────────────────────────────────────────
function renderFanChart(d) {
  const paths  = d.simulation.percentile_paths;
  const T      = paths.p50.length;
  const days   = Array.from({ length: T }, (_, i) => i);
  const v0     = d.meta.portfolio_value_usd;

  const traces = [
    band(days, paths.p5,  paths.p95, 'rgba(88,166,255,0.10)', '5%–95%'),
    band(days, paths.p25, paths.p75, 'rgba(88,166,255,0.20)', '25%–75%'),
    line(days, paths.p50, '#58a6ff', 'Mediana', 2),
    {
      x: days, y: Array(T).fill(v0),
      mode: 'lines', name: 'Wartość startowa',
      line: { color: '#f85149', width: 1.5, dash: 'dash' },
    },
  ];

  Plotly.newPlot('chart-fan', traces, {
    ...PLOTLY_LAYOUT_BASE,
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickprefix: '$', tickformat: ',.0f' },
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: 'Dzień handlowy' },
    showlegend: true,
    legend: { orientation: 'h', y: -0.15 },
  }, PLOTLY_CONFIG);
}

// ── Histogram ─────────────────────────────────────────────────────────────────
function renderHistogram(d) {
  const hist = d.simulation.final_histogram;
  const rm   = d.risk_metrics;
  const v0   = d.meta.portfolio_value_usd;

  const varThresh95 = rm.var_95.threshold_value_usd;
  const varThresh99 = rm.var_99.threshold_value_usd;

  const colors = hist.bins.map(b =>
    b < varThresh99 ? '#f85149' :
    b < varThresh95 ? '#d29922' :
    '#3fb950'
  );

  const traces = [
    {
      x: hist.bins, y: hist.counts,
      type: 'bar', name: 'Symulacje',
      marker: { color: colors },
      width: (hist.bins[1] - hist.bins[0]) * 0.95,
    },
  ];

  const shapes = [
    vline(v0, '#e6edf3', 'Wartość startowa'),
    vline(varThresh95, '#d29922', 'VaR 95%'),
    vline(varThresh99, '#f85149', 'VaR 99%'),
    vline(d.risk_metrics.median_end_usd, '#3fb950', 'Mediana'),
  ];

  Plotly.newPlot('chart-histogram', traces, {
    ...PLOTLY_LAYOUT_BASE,
    bargap: 0.02,
    shapes,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, tickprefix: '$', tickformat: ',.0f' },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: 'Liczba symulacji' },
  }, PLOTLY_CONFIG);
}

// ── Multi-horizon box plot ────────────────────────────────────────────────────
function renderMultiHorizon(horizonData, v0) {
  const labels = { '21': '1 miesiąc', '63': '3 miesiące', '126': '6 miesięcy', '252': '1 rok' };
  const colors  = ['#58a6ff', '#3fb950', '#d29922', '#f85149'];

  const traces = Object.entries(horizonData).map(([h, hd], i) => {
    const pcts  = hd.percentiles;
    const ret   = hd.returns_pct;
    const color = colors[i];
    return {
      type:  'box',
      name:  labels[h] || `${h}d`,
      lowerfence: [parseFloat(pcts['1%'])],
      q1:         [parseFloat(pcts['25%'])],
      median:     [parseFloat(pcts['50%'])],
      q3:         [parseFloat(pcts['75%'])],
      upperfence: [parseFloat(pcts['99%'])],
      mean:       [parseFloat(hd.mean)],
      boxmean:    true,
      marker:     { color },
      line:       { color },
    };
  });

  traces.push({
    x: Object.keys(labels).map(h => labels[h] || `${h}d`),
    y: Array(4).fill(v0),
    mode: 'lines', name: 'Wartość startowa',
    line: { color: '#f85149', dash: 'dash', width: 1.5 },
    showlegend: false,
  });

  Plotly.newPlot('chart-horizon', traces, {
    ...PLOTLY_LAYOUT_BASE,
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickprefix: '$', tickformat: ',.0f' },
    showlegend: false,
  }, PLOTLY_CONFIG);
}

// ── Drawdown ──────────────────────────────────────────────────────────────────
function renderDrawdown(hist) {
  Plotly.newPlot('chart-drawdown', [{
    x: hist.bins, y: hist.counts,
    type: 'bar',
    marker: { color: '#d29922' },
    width: (hist.bins[1] - hist.bins[0]) * 0.95,
  }], {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, title: 'Maks. drawdown (%)', ticksuffix: '%' },
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, title: 'Liczba symulacji' },
  }, PLOTLY_CONFIG);
}

// ── Allocation ────────────────────────────────────────────────────────────────
function renderAllocation(assets) {
  const tickers    = assets.map(a => a.ticker);
  const weights    = assets.map(a => a.weight_pct);
  const riskContrib = assets.map(a => a.weight_pct / 100 * a.vol_annual_pct);
  const totalRisk  = riskContrib.reduce((s, v) => s + v, 0);
  const riskPct    = riskContrib.map(r => round(r / totalRisk * 100, 1));

  Plotly.newPlot('chart-allocation', [
    {
      type: 'bar', orientation: 'h',
      name: 'Waga portfela (%)',
      x: weights, y: tickers,
      marker: { color: '#58a6ff' },
    },
    {
      type: 'bar', orientation: 'h',
      name: 'Wkład w ryzyko (%)',
      x: riskPct, y: tickers,
      marker: { color: '#f85149' },
    },
  ], {
    ...PLOTLY_LAYOUT_BASE,
    barmode: 'group',
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, ticksuffix: '%' },
    legend: { orientation: 'h', y: -0.15 },
    margin: { ...PLOTLY_LAYOUT_BASE.margin, l: 80 },
  }, PLOTLY_CONFIG);
}

// ── Correlation heatmap ───────────────────────────────────────────────────────
function renderCorrelation(corr) {
  Plotly.newPlot('chart-corr', [{
    type: 'heatmap',
    x: corr.tickers, y: corr.tickers, z: corr.matrix,
    colorscale: 'RdYlGn',
    zmin: -1, zmax: 1,
    text: corr.matrix.map(row => row.map(v => v.toFixed(2))),
    texttemplate: '%{text}',
    showscale: true,
    colorbar: { thickness: 12 },
  }], {
    ...PLOTLY_LAYOUT_BASE,
    margin: { t: 20, b: 60, l: 60, r: 20 },
    xaxis: { side: 'bottom', tickangle: -45 },
  }, PLOTLY_CONFIG);
}

// ── Volatility ────────────────────────────────────────────────────────────────
function renderVolatility(assets) {
  const sorted = [...assets].sort((a, b) => b.vol_annual_pct - a.vol_annual_pct);
  const colors = sorted.map(a =>
    a.vol_annual_pct > 80 ? '#f85149' :
    a.vol_annual_pct > 50 ? '#d29922' :
    '#3fb950'
  );

  Plotly.newPlot('chart-vol', [{
    type: 'bar',
    x: sorted.map(a => a.ticker),
    y: sorted.map(a => a.vol_annual_pct),
    marker: { color: colors },
    text: sorted.map(a => `${a.vol_annual_pct}%`),
    textposition: 'outside',
  }], {
    ...PLOTLY_LAYOUT_BASE,
    shapes: [
      hline(50, '#d29922', 'Próg 50%'),
      hline(80, '#f85149', 'Próg 80%'),
    ],
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, ticksuffix: '%', title: 'Roczna vol. (%)' },
  }, PLOTLY_CONFIG);
}

// ── Stress Tests ──────────────────────────────────────────────────────────────
function renderStressTests(tests, v0) {
  const names  = tests.map(t => t.name);
  const shocks = tests.map(t => t.immediate_pnl_pct);
  const medians = tests.map(t =>
    round((t.median_end_usd - t.shocked_value_usd) / t.shocked_value_usd * 100, 1)
  );

  Plotly.newPlot('chart-stress', [
    {
      type: 'bar', name: 'Szok natychmiastowy (%)',
      x: names, y: shocks,
      marker: { color: '#f85149' },
    },
    {
      type: 'bar', name: 'Mediana po 1 roku (%)',
      x: names, y: medians,
      marker: { color: '#58a6ff' },
    },
  ], {
    ...PLOTLY_LAYOUT_BASE,
    barmode: 'group',
    yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, ticksuffix: '%', title: 'Zmiana (%)' },
    shapes: [{ type: 'line', x0: -0.5, x1: names.length - 0.5, y0: 0, y1: 0,
                line: { color: '#e6edf3', width: 1, dash: 'dot' } }],
    legend: { orientation: 'h', y: -0.2 },
    margin: { ...PLOTLY_LAYOUT_BASE.margin, b: 100 },
    xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, tickangle: -15 },
  }, PLOTLY_CONFIG);
}

// ── Assets Table ──────────────────────────────────────────────────────────────
function renderAssetsTable(assets) {
  const tbody = document.getElementById('assets-tbody');
  tbody.innerHTML = assets.map(a => {
    const pnlPct = round((a.price_usd - a.cost_price_local * (a.price_usd / a.price_local)) / (a.cost_price_local * (a.price_usd / a.price_local)) * 100, 1);
    const bsTag  = a.bootstrapped_years > 0
      ? `<span class="bootstrap-tag">+${a.bootstrapped_years}y BS</span>`
      : '';
    return `
      <tr>
        <td>${a.ticker}</td>
        <td>$${a.price_usd.toFixed(4)}</td>
        <td>${a.qty}</td>
        <td>$${fmt(a.value_usd)}</td>
        <td>${a.weight_pct}%</td>
        <td class="${a.vol_annual_pct > 80 ? 'negative' : a.vol_annual_pct > 50 ? 'orange' : 'positive'}">${a.vol_annual_pct}%</td>
        <td class="${a.mu_annual_pct >= 0 ? 'positive' : 'negative'}">${a.mu_annual_pct > 0 ? '+' : ''}${a.mu_annual_pct}%</td>
        <td>${a.nu}</td>
        <td>${a.available_years}${bsTag}</td>
        <td>${a.bootstrapped_years > 0 ? a.bootstrapped_years : '—'}</td>
      </tr>`;
  }).join('');
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n) {
  return parseFloat(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function round(n, d) {
  return Math.round(n * 10 ** d) / 10 ** d;
}

function pnlStr(val, v0) {
  const pct = round((val - v0) / v0 * 100, 1);
  return (pct >= 0 ? '+' : '') + pct + '%';
}

function line(x, y, color, name, width = 1.5) {
  return { x, y, mode: 'lines', name, line: { color, width }, type: 'scatter' };
}

function band(x, y_low, y_high, fillcolor, name) {
  return {
    x: [...x, ...x.slice().reverse()],
    y: [...y_high, ...y_low.slice().reverse()],
    fill: 'toself', fillcolor,
    line: { color: 'transparent' },
    mode: 'lines', name, type: 'scatter', showlegend: true,
  };
}

function vline(x, color, name) {
  return {
    type: 'line', x0: x, x1: x, y0: 0, y1: 1, yref: 'paper',
    line: { color, width: 1.5, dash: 'dot' },
    name,
  };
}

function hline(y, color, name) {
  return {
    type: 'line', x0: 0, x1: 1, xref: 'paper', y0: y, y1: y,
    line: { color, width: 1, dash: 'dash' },
  };
}
