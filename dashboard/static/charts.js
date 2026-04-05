// ARIA Dashboard — Plotly.js chart rendering
// Dark Premium Industrial design system

const C = {
  fail:   "#ef4444",
  pass:   "#22c55e",
  warn:   "#f59e0b",
  accent: "#4f98a3",
  text:   "#e2e8f0",
  muted:  "#94a3b8",
  grid:   "rgba(255,255,255,0.07)",
  bg:     "transparent",
};

const BASE = {
  paper_bgcolor: "transparent",
  plot_bgcolor:  "rgba(255,255,255,0.03)",
  font: { family: "Inter, sans-serif", color: "#e2e8f0", size: 15 },
  showlegend: false,
};

const CFG = { displayModeBar: false, responsive: true, autosize: true };

// ── Overview ──────────────────────────────────────────────────────────────

function renderStatusDonut(data, elementId) {
  const counts = { PASS: 0, WARNING: 0, FAIL: 0 };
  data.forEach(d => { if (d.status in counts) counts[d.status] = d.count; });

  const labels = ["PASS", "WARNING", "FAIL"];
  const values = labels.map(l => counts[l]);
  const total  = values.reduce((a, b) => a + b, 0);
  const failPct = total > 0 ? ((counts.FAIL / total) * 100).toFixed(1) : "0.0";

  Plotly.newPlot(elementId, [{
    type: "pie",
    hole: 0.65,
    labels,
    values,
    marker: {
      colors: [C.pass, C.warn, C.fail],
      line: { color: "#0a0b0f", width: 3 },
    },
    textinfo: "none",
    hovertemplate: "<b>%{label}</b><br>%{value} groups<br>%{percent}<extra></extra>",
  }], {
    ...BASE,
    height: 380,
    margin: { t: 70, b: 80, l: 75, r: 45 },
    showlegend: true,
    legend: {
      orientation: "h",
      x: 0.5, xanchor: "center",
      y: -0.12,
      font: { color: C.text, size: 14 },
      itemgap: 20,
    },
    annotations: [{
      text: `<b>${failPct}%</b><br><span style="font-size:15px;color:#94a3b8">FAIL</span>`,
      x: 0.5, y: 0.5,
      font: { size: 36, color: "#f8fafc", family: "JetBrains Mono, monospace" },
      showarrow: false,
    }],
  }, CFG);
}

function renderInstrumentBar(data, elementId) {
  const instruments = [...new Set(data.map(d => d.instrument_id))].sort();
  const statuses    = ["PASS", "WARNING", "FAIL"];
  const palette     = [C.pass, C.warn, C.fail];

  const traces = statuses.map((s, i) => ({
    name: s,
    type: "bar",
    x: instruments,
    y: instruments.map(inst => {
      const m = data.find(d => d.instrument_id === inst && d.status === s);
      return m ? m.count : 0;
    }),
    marker: { color: palette[i] },
    hovertemplate: `<b>${s}</b>: %{y}<extra></extra>`,
  }));

  Plotly.newPlot(elementId, traces, {
    ...BASE,
    height: 420,
    barmode: "group",
    bargap: 0.25,
    showlegend: true,
    legend: {
      orientation: "h",
      x: 0.5, xanchor: "center",
      y: -0.15,
      font: { color: C.text, size: 14 },
      itemgap: 20,
    },
    margin: { t: 70, b: 80, l: 75, r: 45 },
    xaxis: {
      color: C.muted,
      tickfont: { size: 12, color: C.muted },
      gridcolor: "transparent",
      tickangle: 0,
    },
    yaxis: {
      color: C.muted,
      tickfont: { size: 12, color: C.muted },
      gridcolor: "rgba(255,255,255,0.07)",
      zerolinecolor: "rgba(255,255,255,0.2)",
      title: { text: "Groups", font: { size: 13, color: "#64748b" } },
    },
  }, CFG);
}

// ── Causal page ───────────────────────────────────────────────────────────

function renderATEChart(ates, elementId) {
  const ranked = Object.entries(ates).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const labels = ranked.map(([k]) => k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()));
  const values = ranked.map(([, v]) => v);
  const maxAbsVal = Math.max(...values.map(Math.abs));

  Plotly.newPlot(elementId, [
    {
      // Trace 1: bars — no text/annotations, just colors
      type: "bar",
      orientation: "h",
      x: values,
      y: labels,
      marker: { color: values.map(v => v >= 0 ? "#f87171" : "#22d3ee"), opacity: 0.9 },
      hovertemplate: "<b>%{y}</b><br>ATE: %{x:.4f}<extra></extra>",
      showlegend: false,
    },
    {
      // Trace 2: aligned labels — all at same x, never cut off, never overlapping
      type: "scatter",
      mode: "text",
      x: labels.map(() => maxAbsVal * 1.5),
      y: labels,
      text: ranked.map(([_, val]) => `${val >= 0 ? "+" : ""}${val.toFixed(4)}`),
      textposition: "middle right",
      textfont: { size: 13, color: "#e2e8f0", family: "monospace" },
      hoverinfo: "none",
      showlegend: false,
    }
  ], {
    ...BASE,
    height: 440,
    margin: { t: 50, b: 70, l: 220, r: 20 },
    xaxis: {
      color: C.muted,
      tickfont: { size: 12, color: C.muted },
      gridcolor: "rgba(255,255,255,0.07)",
      zeroline: true,
      zerolinecolor: "rgba(255,255,255,0.3)",
      zerolinewidth: 2,
      range: [-maxAbsVal * 0.3, maxAbsVal * 1.9],
      title: { text: "Average Treatment Effect on Z-Score", font: { size: 13, color: "#64748b" } },
    },
    yaxis: {
      tickfont: { size: 13, color: C.text },
      gridcolor: "transparent",
      automargin: true,
    },
  }, CFG);
}

function renderCausalGraph(elementId) {
  // Fixed 3-tier layout: Tier1=outcome, Tier2=mediators, Tier3=root causes
  const nodes = [
    { id: "qc_fail",          label: "QC Z-Score",       x: 0.50, y: 1.0, tier: 1, hover: "Outcome: the QC z-score result" },
    { id: "lab_temp_c",       label: "Lab Temp (°C)",    x: 0.15, y: 0.5, tier: 2, hover: "Lab temperature — high temp degrades enzymes" },
    { id: "reagent_activity", label: "Reagent Activity", x: 0.50, y: 0.5, tier: 2, hover: "Chemical activity level of the reagent" },
    { id: "drift",            label: "Cal. Drift",       x: 0.85, y: 0.5, tier: 2, hover: "Instrument drift since last calibration" },
    { id: "reagent_lot_id",   label: "Reagent Lot",      x: 0.15, y: 0.0, tier: 3, hover: "Batch ID — some lots are less stable" },
    { id: "humidity_pct",     label: "Humidity %",       x: 0.50, y: 0.0, tier: 3, hover: "Lab relative humidity affects reagents" },
    { id: "hours_since_cal",  label: "Hours Since Cal.", x: 0.85, y: 0.0, tier: 3, hover: "Hours since last instrument calibration" },
  ];

  const tierStyle = {
    1: { color: "#ef4444", border: "#fca5a5", size: 34 },
    2: { color: "#0e7490", border: "#22d3ee", size: 26 },
    3: { color: "#1e293b", border: "#64748b", size: 20 },
  };

  const edges = [
    { from: "reagent_lot_id",   to: "reagent_activity", toOutcome: false },
    { from: "humidity_pct",     to: "reagent_activity", toOutcome: false },
    { from: "lab_temp_c",       to: "reagent_activity", toOutcome: false },
    { from: "hours_since_cal",  to: "drift",            toOutcome: false },
    { from: "lab_temp_c",       to: "qc_fail",          toOutcome: true  },
    { from: "reagent_activity", to: "qc_fail",          toOutcome: true  },
    { from: "drift",            to: "qc_fail",          toOutcome: true  },
  ];

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  // Arrows with standoff=20 so arrowhead stops at node edge, not center
  const arrowAnnotations = edges.map(edge => {
    const s = nodeMap[edge.from], t = nodeMap[edge.to];
    return {
      ax: s.x, ay: s.y,
      x:  t.x, y:  t.y,
      xref: "paper", yref: "paper",
      axref: "paper", ayref: "paper",
      showarrow:  true,
      arrowhead:  2,
      arrowsize:  1.8,
      arrowwidth: edge.toOutcome ? 3 : 2,
      arrowcolor: edge.toOutcome ? "#f87171" : "#38bdf8",
      standoff:   20,
    };
  });

  // Node labels as annotations (away from arrowheads)
  const labelShifts = {
    "qc_fail":          { xshift:   0, yshift:  20 },
    "lab_temp_c":       { xshift: -15, yshift: -20 },
    "reagent_activity": { xshift:   0, yshift: -20 },
    "drift":            { xshift:  15, yshift: -20 },
    "reagent_lot_id":   { xshift: -15, yshift: -20 },
    "humidity_pct":     { xshift:   0, yshift: -20 },
    "hours_since_cal":  { xshift:  15, yshift: -20 },
  };

  const labelAnnotations = nodes.map(n => ({
    x: n.x, y: n.y,
    xref: "paper", yref: "paper",
    text: n.label,
    showarrow: false,
    font: { size: 13, color: "#f1f5f9", family: "Inter, sans-serif" },
    xanchor: "center",
    yanchor: "middle",
    xshift: (labelShifts[n.id] || {}).xshift || 0,
    yshift: (labelShifts[n.id] || {}).yshift || 0,
  }));

  const legendAnnotation = {
    x: 0.5, y: -0.12,
    xref: "paper", yref: "paper",
    text: '<span style="color:#ef4444">●</span> Outcome  <span style="color:#0e7490">●</span> Mediator  <span style="color:#64748b">●</span> Root Cause',
    showarrow: false,
    font: { size: 11, color: "#64748b" },
    xanchor: "center",
    yanchor: "bottom",
  };

  Plotly.newPlot(elementId, [{
    type: "scatter",
    mode: "markers",
    x: nodes.map(n => n.x),
    y: nodes.map(n => n.y),
    customdata: nodes.map(n => n.hover),
    marker: {
      size:  nodes.map(n => tierStyle[n.tier].size),
      color: nodes.map(n => tierStyle[n.tier].color),
      line:  { color: nodes.map(n => tierStyle[n.tier].border), width: 2 },
    },
    hovertemplate: "<b>%{customdata}</b><extra></extra>",
    showlegend: false,
  }], {
    ...BASE,
    height: 480,
    paper_bgcolor: "transparent",
    plot_bgcolor:  "transparent",
    margin: { t: 40, b: 80, l: 60, r: 60 },
    xaxis: { visible: false, range: [-0.12, 1.12] },
    yaxis: { visible: false, range: [-0.20, 1.20] },
    annotations: [...arrowAnnotations, ...labelAnnotations, legendAnnotation],
  }, CFG);
}

// ── Explainer page ──────────────────────────────────────────────────────────

function renderZGauge(zScore, elementId) {
  const absZ  = Math.abs(zScore);
  const color = absZ > 3 ? C.fail : absZ > 2 ? C.warn : C.pass;

  // Use domain to keep gauge arc fully within bounds
  Plotly.newPlot(elementId, [{
    type: "indicator",
    mode: "gauge+number",
    value: Math.round(zScore * 100) / 100,
    domain: { x: [0, 1], y: [0, 1] },
    number: {
      /* 44px — large enough to read at 100% zoom */
      font: { size: 44, color, family: "JetBrains Mono, monospace" },
      suffix: " σ",
    },
    gauge: {
      shape: "angular",
      axis: {
        range: [-4, 4],
        tickvals: [-4, -3, -2, -1, 0, 1, 2, 3, 4],
        ticktext: ["-4", "-3", "-2", "-1", "0", "+1", "+2", "+3", "+4"],
        tickcolor: C.muted,
        tickfont: { color: C.muted, size: 13 },
        linecolor: "rgba(255,255,255,0.1)",
      },
      bar: { color, thickness: 0.22 },
      bgcolor: "rgba(255,255,255,0.02)",
      borderwidth: 0,
      steps: [
        { range: [-4, -2], color: "rgba(224,92,106,0.14)" },
        { range: [-2,  2], color: "rgba(93,168,74,0.10)" },
        { range: [ 2,  4], color: "rgba(224,92,106,0.14)" },
      ],
      threshold: {
        line: { color: "rgba(255,255,255,0.4)", width: 2 },
        thickness: 0.8,
        value: zScore < 0 ? -2 : 2,
      },
    },
  }], {
    ...BASE,
    height: 360,
    margin: { t: 80, b: 30, l: 50, r: 50 },
  }, CFG);
}

// ── Architecture page ────────────────────────────────────────────────────────

function renderDataFlowDiagram(elementId) {
  // 4 pipeline layers — each with a distinct color identity
  const LAYER = {
    0: { fill: "#0e1f4a", border: "#3b82f6", arrow: "#60a5fa", name: "① DATA SOURCES"  },
    1: { fill: "#0a2018", border: "#22c55e", arrow: "#4ade80", name: "② INGESTION"      },
    2: { fill: "#061c28", border: "#22d3ee", arrow: "#67e8f9", name: "③ ANALYTICS"      },
    3: { fill: "#271400", border: "#f59e0b", arrow: "#fbbf24", name: "④ INTERFACE"      },
  };

  const nodes = [
    { id: "mimic",   label: "MIMIC-IV\nPhysioNet",      sub: "Real hospital\nlab reference data",       path: "data/raw/mimic_demo/",       x: 0.10, y: 0.82, layer: 0 },
    { id: "gen",     label: "Synthetic\nGenerator",     sub: "116,640 QC records\n180 days × 3 instr.", path: "data/synthetic/generate.py", x: 0.10, y: 0.42, layer: 0 },
    { id: "loader",  label: "Data\nLoader",             sub: "CSV → DataFrame\ntype coercion + sort",   path: "src/ingestion/loader.py",    x: 0.36, y: 0.62, layer: 1 },
    { id: "rules",   label: "Westgard\nEngine",         sub: "6 rules · 30-day\ntiered windows",        path: "src/qc/rules.py",            x: 0.62, y: 0.82, layer: 2 },
    { id: "causal",  label: "Causal\nEngine",           sub: "DoWhy · ATE\nBackdoor linear reg",        path: "src/causal/engine.py",       x: 0.62, y: 0.42, layer: 2 },
    { id: "api",     label: "FastAPI\nBackend",         sub: "REST + Jinja2\nport 8000",                path: "src/api/main.py",            x: 0.88, y: 0.62, layer: 3 },
    { id: "db",      label: "SQLite\nStorage",          sub: "QC result history\n& persistence",        path: "src/storage/db.py",          x: 0.88, y: 0.88, layer: 3 },
    { id: "dash",    label: "Web\nDashboard",           sub: "5 pages · Plotly.js\ninteractive charts", path: "dashboard/templates/",       x: 0.88, y: 0.36, layer: 3 },
    { id: "mcp",     label: "MCP\nServer",              sub: "AI assistant\nintegration (Claude)",      path: "src/mcp/server.py",          x: 0.62, y: 0.10, layer: 3 },
  ];

  const edges = [
    { from: "mimic",  to: "gen"    },
    { from: "gen",    to: "loader" },
    { from: "loader", to: "rules"  },
    { from: "loader", to: "causal" },
    { from: "rules",  to: "api"    },
    { from: "causal", to: "api"    },
    { from: "api",    to: "db"     },
    { from: "api",    to: "dash"   },
    { from: "api",    to: "mcp"    },
  ];

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  // Arrows colored by source layer, standoff stops at node edge
  const arrowAnnotations = edges.map(e => {
    const s = nodeMap[e.from], t = nodeMap[e.to];
    return {
      ax: s.x, ay: s.y, x: t.x, y: t.y,
      xref: "paper", yref: "paper",
      axref: "paper", ayref: "paper",
      showarrow: true, arrowhead: 2,
      arrowsize: 1.3, arrowwidth: 2,
      arrowcolor: LAYER[s.layer].arrow,
      standoff: 32,
    };
  });

  // Layer header labels at the top of each column
  const layerXPositions = [0.10, 0.36, 0.62, 0.88];
  const headerAnnotations = Object.values(LAYER).map((l, i) => ({
    x: layerXPositions[i], y: 1.05,
    xref: "paper", yref: "paper",
    text: `<b>${l.name}</b>`,
    showarrow: false,
    font: { size: 11, color: l.border, family: "Inter, sans-serif" },
    xanchor: "center",
  }));

  // Node name labels (centered on marker)
  const labelAnnotations = nodes.map(n => ({
    x: n.x, y: n.y,
    xref: "paper", yref: "paper",
    text: n.label.replace("\n", "<br>"),
    showarrow: false,
    font: { size: 13, color: "#f1f5f9", family: "Inter, sans-serif" },
    xanchor: "center",
    yanchor: "middle",
    align: "center",
  }));

  Plotly.newPlot(elementId, [{
    type: "scatter",
    mode: "markers",
    x: nodes.map(n => n.x),
    y: nodes.map(n => n.y),
    text: nodes.map(n => n.label.replace("\n", " ")),
    customdata: nodes.map(n => `<code style="color:#94a3b8">${n.path}</code><br><span style="color:#64748b">${n.sub.replace("\n","  ")}</span>`),
    marker: {
      symbol: "square",
      size: 86,
      color: nodes.map(n => LAYER[n.layer].fill),
      line: { color: nodes.map(n => LAYER[n.layer].border), width: 2 },
      opacity: 0.95,
    },
    hovertemplate: "<b style='color:#f1f5f9'>%{text}</b><br>%{customdata}<extra></extra>",
    showlegend: false,
  }], {
    ...BASE,
    height: 820,
    margin: { t: 55, b: 55, l: 50, r: 50 },
    xaxis: { visible: false, range: [-0.06, 1.06] },
    yaxis: { visible: false, range: [-0.06, 1.12] },
    annotations: [...arrowAnnotations, ...headerAnnotations, ...labelAnnotations],
  }, CFG);
}

function renderToolStackChart(elementId) {
  const categories = ["Data Layer", "Intelligence Layer", "Interface Layer"];
  const catColors   = ["#1d4ed8", "#0e7490", "#b45309"];
  const catBorders  = ["#60a5fa", "#22d3ee", "#fbbf24"];

  const toolsByCat = [
    ["Python 3.11", "pandas / numpy", "MIMIC-IV Demo"],
    ["DoWhy 0.11",  "pgmpy",          "scikit-learn"],
    ["FastAPI",     "Jinja2 + Plotly","SQLite + MCP"],
  ];

  const traces = categories.map((cat, ci) => ({
    type: "bar",
    orientation: "h",
    name: cat,
    x: [1],
    y: [cat],
    marker: {
      color: catColors[ci],
      opacity: 0.88,
      line: { color: catBorders[ci], width: 2 },
    },
    text: [toolsByCat[ci].join("   ·   ")],
    textposition: "inside",
    insidetextanchor: "middle",
    textfont: { size: 14, color: "#f1f5f9", family: "Inter, sans-serif" },
    hovertemplate: `<b>${cat}</b><br>${toolsByCat[ci].join("<br>")}<extra></extra>`,
    width: 0.5,
  }));

  Plotly.newPlot(elementId, traces, {
    ...BASE,
    height: 360,
    barmode: "stack",
    showlegend: false,
    margin: { t: 40, b: 60, l: 200, r: 40 },
    xaxis: { visible: false },
    yaxis: {
      tickfont: { size: 15, color: C.text },
      gridcolor: "transparent",
      automargin: true,
    },
  }, CFG);
}
