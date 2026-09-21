"use strict";

const $ = (id) => document.getElementById(id);
const state = { layout: null, racks: [], cells: new Map(), busy: false, routes: [], nextRoute: 1, activeRoute: null };
const routeColors = ["#2563eb", "#9333ea", "#d97706", "#0891b2", "#be185d", "#4d7c0f"];
const key = (x, y) => `${x},${y}`;
const number = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });

function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}

function connection(online) {
  $("api-status").textContent = online ? "API ● ONLINE" : "API ● UNAVAILABLE";
  $("api-status").className = `api-status ${online ? "online" : "offline"}`;
}

function busy(value) {
  state.busy = value;
  $("route-controls").disabled = value || !state.layout || !state.racks.length;
  $("reload").disabled = value;
  $("editor").disabled = value || !state.layout;
  $("clear-routes").disabled = value;
  $("route-form").setAttribute("aria-busy", String(value));
}

async function request(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    connection(false);
    throw new Error("Cannot reach the API. Check the server and reload the layout.");
  }
  connection(response.status < 500);
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(" · ")
      : data.detail;
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return data;
}

function clearSummary() {
  for (const field of ["source", "destination", "distance", "cable", "steps", "explored", "algorithm", "heuristic"]) {
    $(`result-${field}`).textContent = "—";
  }
  $("summary-note").textContent = "Calculate a route to see its metrics.";
}

function paint() {
  if (!state.layout) return;
  const path = new Map();
  const ordered = [...state.routes.filter((r) => r.id !== state.activeRoute), ...state.routes.filter((r) => r.id === state.activeRoute)];
  for (const saved of ordered) for (const [x, y] of saved.result.route) path.set(key(x, y), saved);
  const blocked = new Set(state.layout.blocked_cells.map(([x, y]) => key(x, y)));
  const source = state.racks.find((rack) => rack.id === $("source").value);
  const destination = state.racks.find((rack) => rack.id === $("destination").value);
  for (const [position, cell] of state.cells) {
    const racks = state.racks.filter((rack) => key(rack.x, rack.y) === position);
    const isSource = source && key(source.x, source.y) === position;
    const isDestination = destination && key(destination.x, destination.y) === position;
    cell.className = "cell";
    cell.classList.toggle("blocked", blocked.has(position));
    cell.classList.toggle("rack", racks.length > 0);
    cell.classList.toggle("route", path.has(position));
    cell.style.setProperty("--route-color", path.get(position)?.color || "#2563eb");
    cell.classList.toggle("source", Boolean(isSource));
    cell.classList.toggle("destination", Boolean(isDestination));
    cell.textContent = isSource && isDestination ? "S/G" : isSource ? "S" : isDestination ? "G" : racks.length ? "R" : "";
    const labels = [blocked.has(position) ? "Blocked" : "Free", ...racks.map((rack) => rack.id)];
    if (path.has(position)) labels.push(`Route ${path.get(position).id}`);
    if (isSource) labels.push("Source");
    if (isDestination) labels.push("Destination");
    cell.title = `(${position}) · ${labels.join(" · ")}`;
    cell.setAttribute("aria-label", cell.title);
  }
  $("grid").setAttribute("aria-label", `${state.layout.width} by ${state.layout.height} data center. Source ${source?.id || "none"}; destination ${destination?.id || "none"}. ${state.routes.length} calculated routes. Overlaps show the selected route color.`);
}

function buildGrid() {
  const grid = $("grid");
  grid.replaceChildren();
  state.cells.clear();
  grid.style.setProperty("--columns", state.layout.width);
  const fragment = document.createDocumentFragment();
  for (let y = 0; y < state.layout.height; y++) {
    for (let x = 0; x < state.layout.width; x++) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.dataset.x = x;
      cell.dataset.y = y;
      state.cells.set(key(x, y), cell);
      fragment.append(cell);
    }
  }
  grid.append(fragment);
  $("layout-meta").textContent = `${state.layout.width} × ${state.layout.height} / ${number.format(state.layout.cell_size_meters)} m per cell`;
  $("map-caption").textContent = `${state.racks.length} racks · ${state.layout.blocked_cells.length} blocked cells`;
  paint();
}

async function load() {
  busy(true);
  clearRoutes();
  clearSummary();
  message("Loading layout and racks…");
  try {
    const [layout, racks] = await Promise.all([request("/api/v1/layout"), request("/api/v1/racks")]);
    state.layout = layout;
    state.racks = racks;
    for (const name of ["source", "destination"]) {
      $(name).replaceChildren(...racks.map((rack) => new Option(rack.id, rack.id)));
    }
    if (racks.length > 1) $("destination").selectedIndex = 1;
    buildGrid();
    message(racks.length ? "Selecione os racks e calcule para adicionar uma rota." : "Sem racks. Use Adicionar rack e clique no mapa.");
  } catch (error) {
    state.layout = null;
    state.racks = [];
    state.cells.clear();
    $("grid").replaceChildren();
    $("grid").setAttribute("aria-label", "Layout unavailable");
    $("source").replaceChildren();
    $("destination").replaceChildren();
    $("layout-meta").textContent = "—";
    $("map-caption").textContent = "Layout unavailable";
    connection(false);
    message(error.message, true);
  } finally {
    busy(false);
  }
}

$("route-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || !state.layout || !$("route-form").reportValidity()) return;
  busy(true);
  clearSummary();
  paint();
  $("calculate").textContent = "Calculating…";
  message("Calculating route…");
  try {
    const result = await request("/api/v1/cable-routes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_rack: $("source").value,
        destination_rack: $("destination").value,
        safety_margin: $("margin").valueAsNumber / 100,
      }),
    });
    const id = state.nextRoute++;
    state.routes.push({ id, result, margin: $("margin").value, color: routeColors[(id - 1) % routeColors.length] });
    state.activeRoute = id;
    renderRoutes();
    showSummary(result);
    paint();
    message(result.steps === 0 ? "Origem e destino compartilham uma posição. Rota adicionada com distância zero." : "Rota adicionada. Selecione outros racks para calcular uma rota adicional.");
  } catch (error) {
    message(error.message, true);
    $("summary-note").textContent = "Não foi possível adicionar a rota. As rotas anteriores continuam na lista.";
  } finally {
    $("calculate").textContent = "Calculate Route ↗";
    busy(false);
  }
});

function showSummary(result) {
  for (const [field, value] of Object.entries({
      source: result.source, destination: result.destination,
      distance: `${number.format(result.distance_meters)} m`,
      cable: `${number.format(result.recommended_cable_length_meters)} m`,
      steps: result.steps, explored: result.explored_nodes,
      algorithm: result.algorithm, heuristic: result.heuristic,
    })) $(`result-${field}`).textContent = value;
    $("summary-note").textContent = "Route calculated. Lengths shown to two decimal places.";
}

function renderRoutes() {
  $("route-list").replaceChildren(...state.routes.map((saved) => {
    const row = document.createElement("li");
    row.className = "route-item";
    row.style.setProperty("--route-color", saved.color);
    const select = document.createElement("button");
    select.className = "route-select";
    select.type = "button";
    select.setAttribute("aria-pressed", String(saved.id === state.activeRoute));
    select.textContent = `Rota ${saved.id}: ${saved.result.source} → ${saved.result.destination}`;
    const info = document.createElement("small");
    info.textContent = `${number.format(saved.result.distance_meters)} m · margem ${saved.margin}%`;
    select.append(info);
    select.addEventListener("click", () => {
      if (state.busy) return;
      state.activeRoute = saved.id;
      $("source").value = saved.result.source;
      $("destination").value = saved.result.destination;
      $("margin").value = saved.margin;
      showSummary(saved.result);
      renderRoutes();
      paint();
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remover rota ${saved.id}`);
    remove.addEventListener("click", () => {
      if (state.busy) return;
      state.routes = state.routes.filter((r) => r.id !== saved.id);
      if (state.activeRoute === saved.id) { state.activeRoute = null; clearSummary(); }
      renderRoutes();
      paint();
    });
    row.append(select, remove);
    return row;
  }));
}

function clearRoutes() {
  state.routes = [];
  state.activeRoute = null;
  clearSummary();
  renderRoutes();
  paint();
}

function refreshSelectors() {
  for (const name of ["source", "destination"]) {
    const previous = $(name).value;
    $(name).replaceChildren(...state.racks.map((rack) => new Option(rack.id, rack.id)));
    if (state.racks.some((rack) => rack.id === previous)) $(name).value = previous;
    else if (name === "destination" && state.racks.length > 1) $(name).selectedIndex = 1;
  }
}

$("grid").addEventListener("click", async (event) => {
  const cell = event.target.closest(".cell");
  if (!cell || state.busy || !state.layout) return;
  const x = Number(cell.dataset.x), y = Number(cell.dataset.y);
  const tool = $("tool").value;
  const rack = state.racks.find((rack) => rack.x === x && rack.y === y);
  if (tool === "inspect") { message(cell.title); return; }
  if (tool === "source" || tool === "destination") {
    if (!rack) { message("Escolha uma célula com rack ou adicione um rack primeiro.", true); return; }
    $(tool).value = rack.id;
    clearSummary();
    paint();
    message(`${tool === "source" ? "Origem" : "Destino"}: ${rack.id}. Calcule para adicionar a rota.`);
    return;
  }
  const edited = structuredClone(state.layout);
  const blocked = edited.blocked_cells.some(([bx, by]) => bx === x && by === y);
  if (tool === "blocked") {
    if (rack) { message("Remova o rack antes de bloquear esta célula.", true); return; }
    edited.blocked_cells = blocked ? edited.blocked_cells.filter(([bx, by]) => bx !== x || by !== y) : [...edited.blocked_cells, [x, y]];
  } else if (tool === "rack") {
    const id = $("rack-id").value.trim();
    if (!id || rack || blocked || state.racks.some((item) => item.id === id)) {
      message("Informe um ID único e selecione uma célula livre, sem rack ou bloqueio.", true); return;
    }
    edited.racks.push({id, x, y});
  } else if (tool === "erase") {
    if (!rack && !blocked) return;
    edited.racks = edited.racks.filter((item) => item.x !== x || item.y !== y);
    edited.blocked_cells = edited.blocked_cells.filter(([bx, by]) => bx !== x || by !== y);
  }
  busy(true);
  message("Aplicando edição…");
  try {
    const updated = await request("/api/v1/layout", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(edited)});
    state.layout = updated;
    state.racks = updated.racks;
    refreshSelectors();
    clearRoutes();
    buildGrid();
    if (tool === "rack") $("rack-id").value = "";
    message("Layout atualizado. Rotas anteriores foram limpas; calcule novamente.");
  } catch (error) { message(error.message, true); }
  finally { busy(false); }
});

$("clear-routes").addEventListener("click", () => { if (!state.busy) clearRoutes(); });

for (const name of ["source", "destination", "margin"]) {
  $(name).addEventListener("input", () => {
    clearSummary();
    paint();
    message("Calcule para adicionar uma rota com os novos parâmetros. Rotas anteriores continuam visíveis.");
  });
}
$("reload").addEventListener("click", load);
load();
