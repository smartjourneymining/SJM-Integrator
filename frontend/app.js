"use strict";

// Node fill colors by label.
const COLORS = {
  Event: "#E3F2FD",
  Touchpoint: "#C8E6C9",
  Entity: "#FFF9C4",
  Journey: "#FFCCBC",
  Log: "#F8BBD0",
  Channel: "#E0E0E0",
  Experience: "#E1BEE7",
  Object: "#D7CCC8",
};

const CY_STYLE = [
  {
    selector: "node",
    style: {
      label: "data(displayLabel)",
      "background-color": (ele) => COLORS[ele.data("label")] || "#ffffff",
      "border-width": 1,
      "border-color": "#94a3b8",
      "font-size": 10,
      "text-valign": "center",
      "text-halign": "center",
      "text-wrap": "wrap",
      "text-max-width": 90,
      width: 46,
      height: 46,
    },
  },
  {
    selector: "edge",
    style: {
      label: "data(label)",
      "font-size": 8,
      color: "#64748b",
      width: 1.5,
      "line-color": "#cbd5e1",
      "target-arrow-color": "#cbd5e1",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
    },
  },
  { selector: "node:selected", style: { "border-width": 3, "border-color": "#2563eb" } },
];

// Register the dagre layout extension if it loaded (UMD global name varies).
let hasDagre = false;
try {
  const ext = window.cytoscapeDagre || window.cytoscapeDagre_;
  if (ext) {
    cytoscape.use(ext);
    hasDagre = true;
  }
} catch (e) {
  hasDagre = false;
}

function runLayout(inst) {
  const opts = hasDagre
    ? { name: "dagre", rankDir: "LR", nodeSep: 30, rankSep: 60 }
    : { name: "breadthfirst", directed: true, spacingFactor: 1.2 };
  try {
    inst.layout(opts).run();
  } catch (e) {
    inst.layout({ name: "cose", animate: false }).run();
  }
}

function decorate(n) {
  const d = n.data;
  d.displayLabel = d.Label || d.EventType || d.journey || d.Channel || d.name || d.label;
  return { data: d };
}

// Build a Cytoscape instance bound to a container + its own sidebar.
function makeCy(containerId, sidebarId) {
  const inst = cytoscape({
    container: document.getElementById(containerId),
    style: CY_STYLE,
  });
  inst.on("tap", "node", (evt) => showNodeProperties(sidebarId, evt.target.data()));
  inst.on("tap", (evt) => {
    if (evt.target === inst) hideSidebar(sidebarId);
    hideCtxMenu();
  });
  inst.on("cxttap", "node", (evt) => {
    if (evt.originalEvent) evt.originalEvent.preventDefault();
    showCtxMenu(inst, sidebarId, evt.target, evt.originalEvent);
  });
  return inst;
}

function renderGraph(inst, data) {
  const nodes = (data.nodes || []).map(decorate);
  inst.elements().remove();
  inst.add(nodes);
  const ids = new Set(nodes.map((n) => n.data.id));
  const edges = (data.edges || [])
    .filter((e) => ids.has(e.data.source) && ids.has(e.data.target))
    .map((e) => ({ data: e.data }));
  inst.add(edges);
  runLayout(inst);
  return nodes.length;
}

// Add nodes/edges to an existing graph (for neighbor expansion).
function mergeGraph(inst, data) {
  const have = new Set(inst.nodes().map((n) => n.id()));
  const newNodes = (data.nodes || []).filter((n) => !have.has(n.data.id)).map(decorate);
  inst.add(newNodes);
  const ids = new Set(inst.nodes().map((n) => n.id()));
  const haveE = new Set(inst.edges().map((e) => e.id()));
  const newEdges = (data.edges || [])
    .filter((e) => !haveE.has(e.data.id) && ids.has(e.data.source) && ids.has(e.data.target))
    .map((e) => ({ data: e.data }));
  inst.add(newEdges);
  runLayout(inst);
  return newNodes.length;
}

function showNodeProperties(sidebarId, data) {
  const sidebar = document.getElementById(sidebarId);
  const tbl = sidebar.querySelector(".node-props");
  tbl.innerHTML = "";
  Object.keys(data).sort().forEach((k) => {
    if (k === "displayLabel") return;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(k)}</td><td>${escapeHtml(String(data[k]))}</td>`;
    tbl.appendChild(tr);
  });
  sidebar.classList.remove("hidden");
}
function hideSidebar(sidebarId) {
  document.getElementById(sidebarId).classList.add("hidden");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function setStatus(id, msg, isError) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.style.color = isError ? "#dc2626" : "#64748b";
}

// --- Context menu (native right-click) ---
const ctx = document.getElementById("ctxmenu");

function hideCtxMenu() { ctx.classList.add("hidden"); }

function showCtxMenu(inst, sidebarId, node, oe) {
  const d = node.data();
  const items = [
    { label: "View properties", fn: () => showNodeProperties(sidebarId, d) },
    { label: "Expand neighbors", fn: () => expandNeighbors(inst, d.id) },
    { label: "Hide this node", fn: () => node.remove() },
    { label: "Hide others", fn: () => inst.nodes().not(node).remove() },
  ];
  if (d.journey) {
    items.push({ label: `Focus journey ${d.journey}`, fn: () => showJourney(d.journey) });
  }
  ctx.innerHTML = "";
  items.forEach((it) => {
    const b = document.createElement("button");
    b.textContent = it.label;
    b.onclick = () => { hideCtxMenu(); it.fn(); };
    ctx.appendChild(b);
  });
  const x = oe ? oe.clientX : 100;
  const y = oe ? oe.clientY : 100;
  ctx.style.left = x + "px";
  ctx.style.top = y + "px";
  ctx.classList.remove("hidden");
}

document.addEventListener("click", hideCtxMenu);
window.addEventListener("blur", hideCtxMenu);

async function expandNeighbors(inst, gid) {
  try {
    const res = await fetch(`/api/neighbors/${gid}`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    mergeGraph(inst, data);
  } catch (e) {
    console.error("expand failed", e);
  }
}

// Two independent graph views.
let cyGraph = null;
let cyQuery = null;

// --- Tabs ---
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (cyGraph) cyGraph.resize();
    if (cyQuery) cyQuery.resize();
  });
});

// --- Graph tab ---
document.getElementById("btn-load-graph").addEventListener("click", async () => {
  const limit = document.getElementById("graph-limit").value || 500;
  setStatus("graph-status", "Loading…");
  try {
    const res = await fetch(`/api/graph?limit=${limit}`);
    const data = await res.json();
    const n = renderGraph(cyGraph, data);
    setStatus("graph-status", `${n} nodes, ${data.edges.length} edges${data.limited ? " (limited)" : ""}`);
  } catch (e) {
    setStatus("graph-status", "Failed: " + e, true);
  }
});

async function showJourney(jid) {
  setStatus("graph-status", `Loading journey ${jid}…`);
  try {
    const res = await fetch(`/api/journey/${encodeURIComponent(jid)}`);
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    document.querySelector('.tab[data-tab="graph"]').click();
    const n = renderGraph(cyGraph, data);
    document.getElementById("journey-select").value = jid;
    setStatus("graph-status", `journey ${jid}: ${n} nodes, ${data.edges.length} edges`);
  } catch (e) {
    setStatus("graph-status", "Failed: " + e.message, true);
  }
}

document.getElementById("btn-show-journey").addEventListener("click", () => {
  const jid = document.getElementById("journey-select").value;
  if (jid) showJourney(jid);
});

async function loadJourneys() {
  try {
    const res = await fetch("/api/journeys");
    const data = await res.json();
    const sel = document.getElementById("journey-select");
    sel.innerHTML = '<option value="">— all —</option>';
    data.journeys.forEach((j) => {
      const o = document.createElement("option");
      o.value = j;
      o.textContent = j;
      sel.appendChild(o);
    });
  } catch (e) {
    /* no journeys yet */
  }
}

// --- Query tab (own canvas) ---
document.getElementById("preset").addEventListener("change", (e) => {
  if (e.target.value) document.getElementById("query-input").value = e.target.value;
});
document.getElementById("btn-run-query").addEventListener("click", async () => {
  const q = document.getElementById("query-input").value.trim();
  if (!q) return;
  setStatus("query-status", "Running…");
  try {
    const res = await fetch(`/api/query?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    cyQuery.resize();
    const n = renderGraph(cyQuery, data);
    setStatus("query-status", `${n} nodes, ${data.edges.length} edges`);
  } catch (e) {
    setStatus("query-status", "Failed: " + e.message, true);
  }
});

// --- Import tab ---
document.getElementById("btn-import").addEventListener("click", async () => {
  const fileInput = document.getElementById("import-file");
  if (!fileInput.files.length) { setStatus("import-status", "Choose a file first", true); return; }
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  setStatus("import-status", "Importing… (this can take a while)");
  try {
    const res = await fetch("/api/import", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    setStatus("import-status", `Done: ${data.rows} rows`);
    document.getElementById("import-summary").textContent = JSON.stringify(data.summary, null, 2);
    loadJourneys(); // refresh the journey filter
  } catch (e) {
    setStatus("import-status", "Failed: " + e.message, true);
  }
});

// --- Config tab (interactive editor) ---
let cfgSchema = null;
let fileColumns = [];
let fileSamples = {};

function standardFields(extra) {
  const set = new Set(cfgSchema ? cfgSchema.standard_fields : []);
  (extra || []).forEach((f) => set.add(f));
  return [...set].sort();
}

function updateColList() {
  const dl = document.getElementById("col-list");
  dl.innerHTML = "";
  fileColumns.forEach((c) => {
    const o = document.createElement("option");
    o.value = c;
    dl.appendChild(o);
  });
}

function buildMapTable(pre) {
  const mappings = pre.mappings || {};
  const statics = pre.static_values || {};
  const autos = pre.auto_generate || {};
  const skips = new Set(pre.skip_fields || []);
  const gens = cfgSchema ? cfgSchema.generation_types : [];
  const fields = standardFields([
    ...Object.keys(mappings), ...Object.keys(statics), ...Object.keys(autos), ...skips,
  ]);

  const tbl = document.getElementById("map-table");
  tbl.innerHTML =
    "<tr><th>Standard field</th><th>Source column</th><th>Static value</th>" +
    "<th>Auto-generate</th><th class='center'>Skip</th></tr>";
  fields.forEach((f) => {
    const tr = document.createElement("tr");
    tr.dataset.field = f;
    tr.className = "map-row";
    const genOpts = ["", ...gens]
      .map((g) => `<option ${g === (autos[f] || "") ? "selected" : ""}>${escapeHtml(g)}</option>`)
      .join("");
    const sampleCol = mappings[f] && fileSamples[mappings[f]];
    const sample = sampleCol ? ` <span class="sample">e.g. ${escapeHtml(sampleCol)}</span>` : "";
    tr.innerHTML =
      `<td class="fieldname">${escapeHtml(f)}</td>` +
      `<td><input type="text" list="col-list" class="src" value="${escapeHtml(mappings[f] || "")}" placeholder="column…">${sample}</td>` +
      `<td><input type="text" class="static" value="${escapeHtml(statics[f] || "")}"></td>` +
      `<td><select class="gen">${genOpts}</select></td>` +
      `<td class="center"><input type="checkbox" class="skip" ${skips.has(f) ? "checked" : ""}></td>`;
    tbl.appendChild(tr);
  });
}

function buildSchemaTable(settings) {
  const cur = {};
  ["Actor", "Entity", "Event", "Log", "Rating", "Object"].forEach((key) => {
    (settings[key] || []).forEach((fd) => { cur[fd.name] = fd; });
  });
  const cats = cfgSchema ? cfgSchema.categories : [];
  const etypes = cfgSchema ? cfgSchema.entity_types : [];
  const defaults = cfgSchema ? cfgSchema.defaults : {};
  const fields = standardFields(Object.keys(cur));

  const tbl = document.getElementById("schema-table");
  tbl.innerHTML =
    "<tr><th>Field</th><th>Category</th><th class='center'>Identifier</th>" +
    "<th class='center'>Foreign key</th><th>Key relates to</th><th>Actor type</th></tr>";
  fields.forEach((f) => {
    const d = cur[f] || defaults[f] || {};
    const cat = d.type_map || d.category || "";
    const opt = (list, sel) =>
      ["", ...list].map((c) => `<option ${c === sel ? "selected" : ""}>${escapeHtml(c)}</option>`).join("");
    const tr = document.createElement("tr");
    tr.dataset.field = f;
    tr.className = "schema-row";
    tr.innerHTML =
      `<td class="fieldname">${escapeHtml(f)}</td>` +
      `<td><select class="cat">${opt(cats, cat)}</select></td>` +
      `<td class="center"><input type="checkbox" class="ident" ${d.identifier ? "checked" : ""}></td>` +
      `<td class="center"><input type="checkbox" class="fk" ${d.foreign_key ? "checked" : ""}></td>` +
      `<td><select class="totype">${opt(cats, d.to_type || "")}</select></td>` +
      `<td><select class="etype">${opt(etypes, d.entity_type || "")}</select></td>`;
    tbl.appendChild(tr);
  });
}

function collectConfig() {
  const mappings = {}, static_values = {}, auto_generate = {}, skip_fields = [];
  document.querySelectorAll("#map-table tr.map-row").forEach((tr) => {
    const f = tr.dataset.field;
    if (tr.querySelector(".skip").checked) { skip_fields.push(f); return; }
    const src = tr.querySelector(".src").value.trim();
    const stat = tr.querySelector(".static").value.trim();
    const gen = tr.querySelector(".gen").value;
    if (src) mappings[f] = src;
    if (stat) static_values[f] = stat;
    if (gen) auto_generate[f] = gen;
  });
  const preprocessing = {
    mappings, static_values, auto_generate, skip_fields, csv_columns: fileColumns.slice(),
  };

  const settings = { Actor: [], Event: [], Log: [], Rating: [], Object: [] };
  document.querySelectorAll("#schema-table tr.schema-row").forEach((tr) => {
    const cat = tr.querySelector(".cat").value;
    if (!cat) return;
    const key = cat === "Entity" ? "Actor" : cat;
    settings[key].push({
      name: tr.dataset.field,
      type_map: cat,
      identifier: tr.querySelector(".ident").checked ? 1 : 0,
      foreign_key: tr.querySelector(".fk").checked ? 1 : 0,
      to_type: tr.querySelector(".totype").value,
      entity_type: tr.querySelector(".etype").value,
    });
  });
  return { settings, preprocessing };
}

function updatePreview() {
  const { settings, preprocessing } = collectConfig();
  document.getElementById("settings-json").value = JSON.stringify(settings, null, 4);
  document.getElementById("preprocessing-json").value = JSON.stringify(preprocessing, null, 4);
}

async function loadConfig() {
  setStatus("config-status", "Loading…");
  try {
    const [cfgRes, schRes] = await Promise.all([fetch("/api/config"), fetch("/api/schema")]);
    const cfg = await cfgRes.json();
    cfgSchema = await schRes.json();
    const pre = cfg.preprocessing || {};
    if (!fileColumns.length && Array.isArray(pre.csv_columns)) {
      fileColumns = pre.csv_columns.slice();
    }
    updateColList();
    buildMapTable(pre);
    buildSchemaTable(cfg.settings || {});
    updatePreview();
    setStatus("config-status", "Loaded");
  } catch (e) {
    setStatus("config-status", "Failed: " + e, true);
  }
}

async function loadColumns() {
  const fi = document.getElementById("config-file");
  if (!fi.files.length) { setStatus("config-status", "Choose a file first", true); return; }
  const fd = new FormData();
  fd.append("file", fi.files[0]);
  setStatus("config-status", "Reading columns…");
  try {
    const res = await fetch("/api/inspect", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    fileColumns = data.columns;
    fileSamples = data.samples || {};
    updateColList();
    buildMapTable(collectConfig().preprocessing); // keep current selections, refresh hints
    setStatus("config-status", `${data.columns.length} columns from ${fi.files[0].name}`);
  } catch (e) {
    setStatus("config-status", "Failed: " + e.message, true);
  }
}

async function saveConfig() {
  setStatus("config-status", "Saving…");
  try {
    const res = await fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectConfig()),
    });
    if (!res.ok) throw new Error(res.statusText);
    updatePreview();
    setStatus("config-status", "Saved");
  } catch (e) {
    setStatus("config-status", "Failed: " + e.message, true);
  }
}

document.getElementById("btn-load-columns").addEventListener("click", loadColumns);
document.getElementById("btn-config-reload").addEventListener("click", loadConfig);
document.getElementById("btn-config-save").addEventListener("click", saveConfig);
document.getElementById("toggle-raw").addEventListener("change", (e) => {
  document.getElementById("config-raw").classList.toggle("hidden", !e.target.checked);
  if (e.target.checked) updatePreview();
});

// --- init ---
cyGraph = makeCy("cy", "sidebar");
cyQuery = makeCy("cy-query", "sidebar-query");
loadConfig();
loadJourneys();
