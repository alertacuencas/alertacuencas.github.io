"use strict";

// Maqueta "el río hoy": leer (carteles) → entender (tu lugar, el río) → avisar (etapa 2).
// Todo texto que viene de una fuente externa se inserta con textContent, nunca como HTML.

const COLOR = {
  evacuacion: "var(--urucum)", alerta: "var(--ocre)", normal: "var(--monte)", sin: "var(--sin-dato)",
  rojo: "var(--urucum)", naranja: "#d9661b", amarillo: "var(--ocre)", verde: "var(--monte)",
};
const HEX = { evacuacion: "#b3261e", alerta: "#e0a526", normal: "#3f6b3a", rojo: "#b3261e", naranja: "#d9661b", amarillo: "#e0a526", verde: "#3f6b3a" };
const GRAVEDAD = { evacuacion: 0, alerta: 1, normal: 2 };
const SMN_GRAVEDAD = { rojo: 0, naranja: 1, amarillo: 2, verde: 3 };
const SMN_TXT = { rojo: "Alerta roja", naranja: "Alerta naranja", amarillo: "Alerta amarilla", verde: "Sin alertas" };
const NIVEL_TXT = { evacuacion: "Evacuación", alerta: "Alerta", normal: "Normal" };
const RIOS_DELTA = new Set(["PARANADELASPALMAS", "PARANAGUAZU", "PARANAIBICUY", "DELTA PARANA"]);
const ATAJOS = ["Santa Fe", "Paraná", "Rosario", "Corrientes", "Costa y Delta", "Matanza-Riachuelo"];
const NORMALES_VISIBLES = 5;
const TZ = "America/Argentina/Buenos_Aires";
// Deben coincidir con alertas/estado.py, alertas/serie.py y alertas/fuentes/prefectura.py (docs/contrato-estado.md).
const VERSIONES = { estado: 1, serie: 1, parana: 1 };
const DATO_VIEJO_MIN = 45; // el poll debería correr cada ~10 min

const fmtDia = new Intl.DateTimeFormat("es-AR", { weekday: "long", day: "numeric", month: "long", timeZone: TZ });
const fmtCuando = new Intl.DateTimeFormat("es-AR", { weekday: "long", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TZ });
const fmtHora = new Intl.DateTimeFormat("es-AR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });

const datos = { parana: null, estado: null, serie: null, zonas: null };

// ── Utilidades ──
function el(tag, props = {}, ...hijos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "dataset") Object.assign(n.dataset, v);
    else if (k === "style") for (const [p, val] of Object.entries(v)) n.style.setProperty(p, val);
    else if (k.startsWith("aria") || k === "role") n.setAttribute(k.replace(/^aria([A-Z])/, (_, c) => `aria-${c.toLowerCase()}`), v);
    else n[k] = v;
  }
  for (const h of hijos) if (h != null && h !== false) n.append(h);
  return n;
}
// "martes 17 a las 08:59 h"
const cuando = (ts) => {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  const p = Object.fromEntries(fmtCuando.formatToParts(d).map((x) => [x.type, x.value]));
  return `${p.weekday} ${p.day} a las ${p.hour}:${p.minute} h`;
};
const m = (v) => `${v.toFixed(2).replace(".", ",")} m`;
function distancia(v) {
  const cm = Math.round(Math.abs(v) * 100);
  return cm >= 100 ? m(Math.abs(v)) : `${cm} cm`;
}
function enumerar(lista) {
  if (lista.length <= 1) return lista[0] ?? "";
  return `${lista.slice(0, -1).join(", ")} y ${lista.at(-1)}`;
}
async function cargar(url) {
  const r = await fetch(`${url}?t=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

// ── Lenguaje claro sobre un puerto ──
function porGravedad(a, b) {
  return (a.viejo - b.viejo) || (GRAVEDAD[a.nivel] - GRAVEDAD[b.nivel]) || (b.altura / b.evacuacion - a.altura / a.evacuacion);
}
function fraseNivel(p) {
  if (p.nivel === "evacuacion") return `Pasa por ${distancia(p.altura - p.evacuacion)} el nivel de evacuación (${m(p.evacuacion)}).`;
  if (p.nivel === "alerta") return `Pasó el nivel de alerta. Faltan ${distancia(p.evacuacion - p.altura)} para el de evacuación (${m(p.evacuacion)}).`;
  return `Faltan ${distancia(p.alerta - p.altura)} para el nivel de alerta (${m(p.alerta)}).`;
}
function fraseCorta(p) {
  if (p.nivel === "evacuacion") return `pasa por ${distancia(p.altura - p.evacuacion)} la evacuación`;
  if (p.nivel === "alerta") return `a ${distancia(p.evacuacion - p.altura)} de la evacuación`;
  return `a ${distancia(p.alerta - p.altura)} del alerta`;
}
function fraseTendencia(p) {
  if (p.variacion == null) return "";
  if (p.tendencia === "estable") return "Desde la lectura anterior se mantiene igual.";
  return `Desde la lectura anterior ${p.variacion > 0 ? "subió" : "bajó"} ${distancia(p.variacion)}.`;
}
const flecha = (p) => ({ sube: " · ▲ sube", baja: " · ▼ baja", estable: " · estable" }[p.tendencia] ?? "");

// ── La escala: vara hidrométrica con el agua hasta la altura de hoy ──
function escala(p, clase = "") {
  const tope = Math.max(p.evacuacion * 1.15, p.altura * 1.04);
  const pct = (v) => `${Math.max(0, Math.min(100, (v / tope) * 100)).toFixed(1)}%`;
  const agua = el("span", { className: "escala-agua" });
  requestAnimationFrame(() => requestAnimationFrame(() => { agua.style.height = pct(p.altura); }));
  return el("span", { className: `escala ${clase}`, dataset: { nivel: p.nivel }, role: "img",
    ariaLabel: `${m(p.altura)}; alerta ${m(p.alerta)}, evacuación ${m(p.evacuacion)}` },
    el("span", { className: "escala-vara" }, agua),
    el("span", { className: "escala-marca escala-marca--alerta", style: { bottom: pct(p.alerta) } }),
    el("span", { className: "escala-marca escala-marca--evac", style: { bottom: pct(p.evacuacion) } }));
}

// ── 1 · Hoy: titular y tres carteles ──
const ICONO = {
  rio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 8c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2"/><path d="M2 13c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2"/><path d="M2 18c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2"/></svg>',
  costa: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11l5-5 5 5"/><path d="M6 9v4h6V9"/><path d="M2 18c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2"/></svg>',
  lluvia: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 15a4 4 0 1 1 1-7.9A5 5 0 0 1 18 9a3 3 0 0 1 0 6z"/><path d="M8 19l-1 2M12 19l-1 2M16 19l-1 2"/></svg>',
};

function cartel({ icono, zona, nivel, estado, frase, ir, destino, grande }) {
  const a = el("a", { className: `cartel${grande ? " cartel--grande" : ""}`, href: destino, style: { "--c": COLOR[nivel] } });
  const ic = el("span", { className: "cartel-icono", ariaHidden: "true" });
  ic.innerHTML = ICONO[icono]; // SVG propio, no viene de fuentes externas
  a.append(
    el("span", { className: "cartel-cabeza" }, ic, el("span", {},
      el("span", { className: "cartel-zona", textContent: zona }),
      el("span", { className: "cartel-estado", textContent: estado }))),
    el("p", { className: "cartel-frase", textContent: frase }),
    el("span", { className: "cartel-ir", textContent: `${ir} →` }));
  return a;
}

function resumenParana() {
  const ps = (datos.parana?.puertos ?? []).filter((p) => !p.viejo);
  const evac = ps.filter((p) => p.nivel === "evacuacion");
  const alerta = ps.filter((p) => p.nivel === "alerta");
  return { ps, evac, alerta, nivel: evac.length ? "evacuacion" : alerta.length ? "alerta" : ps.length ? "normal" : "sin" };
}

function resumenCosta() {
  const delta = (datos.parana?.puertos ?? []).filter((p) => RIOS_DELTA.has(p.rio) && !p.viejo).sort(porGravedad);
  const res = datos.serie?.estaciones?.SFER?.residuo?.at(-1);
  const prono = datos.estado?.pronostico_san_fernando;
  const peor = delta[0];
  return { delta, res, prono, nivel: peor ? peor.nivel : "sin" };
}

function resumenLluvia() {
  const zonas = Object.values(datos.estado?.zonas ?? {});
  const conAlerta = zonas.filter((z) => z.alertas.length).sort((a, b) => SMN_GRAVEDAD[a.nivel_smn] - SMN_GRAVEDAD[b.nivel_smn]);
  return { zonas, conAlerta, nivel: conAlerta[0]?.nivel_smn ?? (zonas.length ? "verde" : "sin") };
}

function pintarHoy() {
  const P = resumenParana(), C = resumenCosta(), L = resumenLluvia();
  document.getElementById("hoy-fecha").textContent = fmtDia.format(new Date());
  pintarFrescura();

  // Titular: una sola oración que se entiende sin leer nada más.
  const t = document.getElementById("t-hoy");
  t.replaceChildren();
  if (P.evac.length) {
    t.append("El Paraná está en ", el("em", { textContent: "evacuación" }),
      ` en ${P.evac.length} ${P.evac.length === 1 ? "ciudad" : "ciudades"}. `);
  } else if (P.alerta.length) {
    t.append("El Paraná está en ", el("em", { textContent: "alerta" }), ` en ${P.alerta.length} puertos. `);
  } else if (P.ps.length) {
    t.append("El Paraná está normal. ");
  }
  t.append(C.nivel === "normal" || C.nivel === "sin" ? "En Buenos Aires y el Delta, el río está tranquilo." : "Atención en el Delta.");
  if (L.conAlerta.length) {
    const ev = L.conAlerta[0].alertas[0].evento.toLowerCase();
    t.append(" ", el("span", { className: "titular-extra", textContent: `Hay ${SMN_TXT[L.conAlerta[0].nivel_smn].toLowerCase()} por ${ev} en el AMBA.` }));
  }

  const carteles = [];
  if (P.ps.length) {
    const tramo = P.evac.length > 1 ? `de ${P.evac[0].puerto} a ${P.evac.at(-1).puerto}` : P.evac[0]?.puerto;
    const ordenRio = [...P.evac].sort((a, b) => datos.parana.puertos.indexOf(a) - datos.parana.puertos.indexOf(b));
    carteles.push(cartel({
      icono: "rio", zona: "Río Paraná", nivel: P.nivel, estado: NIVEL_TXT[P.nivel] ?? "Sin datos", grande: true,
      frase: P.evac.length
        ? `El río pasa el nivel de evacuación en ${enumerar(ordenRio.map((p) => p.puerto))}.`
          + (P.alerta.length ? ` ${P.alerta.length} puertos más están en alerta.` : "")
        : P.alerta.length ? `En alerta: ${enumerar(P.alerta.map((p) => p.puerto))}.` : "Ningún puerto está en alerta.",
      ir: tramo ? "Ver ciudad por ciudad" : "Ver el río", destino: "#rio",
    }));
  }
  const res = C.res?.[1];
  carteles.push(cartel({
    icono: "costa", zona: "Buenos Aires y el Delta", nivel: C.nivel,
    estado: C.nivel === "sin" ? "Sin datos" : NIVEL_TXT[C.nivel],
    frase: [
      res == null ? "" : res >= 0 ? `El agua está ${distancia(res)} más alta que la marea de todos los días.` : `El agua está ${distancia(res)} por debajo de la marea de todos los días.`,
      C.delta.length ? (C.nivel === "normal" ? "Ninguna escala del Delta está en alerta." : `En el Delta: ${enumerar(C.delta.filter((p) => p.nivel !== "normal").map((p) => p.puerto))} en ${NIVEL_TXT[C.nivel].toLowerCase()}.`) : "",
    ].join(" ").trim() || "Sin datos recientes del río.",
    ir: "Ver la costa", destino: "#tu-lugar",
  }));
  const a0 = L.conAlerta[0]?.alertas[0];
  carteles.push(cartel({
    icono: "lluvia", zona: "Lluvia y tormentas · AMBA", nivel: L.nivel, estado: SMN_TXT[L.nivel] ?? "Sin datos",
    frase: a0
      ? `${SMN_TXT[L.conAlerta[0].nivel_smn]} por ${a0.evento.toLowerCase()} hasta el ${cuando(a0.expira)} en ${enumerar(L.conAlerta.map((z) => z.nombre))}.`
      : "El Servicio Meteorológico no tiene alertas para las cuencas del AMBA.",
    ir: "Ver tu barrio", destino: "#tu-lugar",
  }));
  const caja = document.getElementById("carteles");
  caja.replaceChildren(...carteles);
  // El cartel de la costa abre directamente la ficha de "Costa y Delta".
  caja.children[carteles.length - 2]?.addEventListener("click", () => mostrarLugar("Costa y Delta"));
}

// Cuánto hace que se actualizaron los datos, a la vista: sin esto un dato viejo parece de ahora.
function hace(min) {
  if (min < 2) return "recién";
  if (min < 60) return `hace ${min} minutos`;
  const h = Math.round(min / 60);
  return h === 1 ? "hace 1 hora" : `hace ${h} horas`;
}
function pintarFrescura() {
  const caja = document.getElementById("frescura");
  const gen = datos.estado?.generado;
  if (!gen) { caja.textContent = "No pudimos cargar los datos. Reintentamos en unos minutos."; caja.dataset.viejo = "true"; return; }
  const min = Math.round((Date.now() - new Date(gen).getTime()) / 60_000);
  const viejo = min > DATO_VIEJO_MIN;
  caja.dataset.viejo = String(viejo);
  caja.textContent = viejo
    ? `⚠ Los datos se actualizaron por última vez ${hace(min)} (${cuando(gen)}). Puede que el río haya cambiado desde entonces.`
    : `Datos actualizados ${hace(min)}.`;
}

// ── 2 · Tu lugar ──
function lugares() {
  const ps = (datos.parana?.puertos ?? []).map((p) => ({ nombre: p.puerto, tipo: "puerto", p }));
  const zs = Object.entries(datos.estado?.zonas ?? {}).map(([id, z]) => ({ nombre: z.nombre, tipo: "zona", id, z }));
  return [...ps, ...zs];
}
const sinTildes = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

function pintarBuscador() {
  const todos = lugares();
  document.getElementById("lugares").replaceChildren(...todos.map((l) => el("option", { value: l.nombre })));
  const atajos = ATAJOS.map((n) => todos.find((l) => l.nombre === n)).filter(Boolean);
  document.getElementById("atajos").replaceChildren(...atajos.map((l) => {
    const nivel = l.tipo === "puerto" ? (l.p.viejo ? "sin" : l.p.nivel) : l.z.nivel_smn;
    const b = el("button", { type: "button", dataset: { lugar: l.nombre }, ariaPressed: "false", style: { "--c": COLOR[nivel] } },
      el("span", { className: "punto", ariaHidden: "true" }), l.nombre);
    b.addEventListener("click", () => mostrarLugar(l.nombre));
    return b;
  }));
}

function mostrarLugar(nombre, { desplazar = true } = {}) {
  const l = lugares().find((x) => sinTildes(x.nombre) === sinTildes(nombre));
  const ficha = document.getElementById("ficha");
  for (const b of document.querySelectorAll("#atajos button")) b.setAttribute("aria-pressed", String(b.dataset.lugar === l?.nombre));
  if (!l) {
    ficha.hidden = false;
    ficha.className = "ficha ficha-zona";
    ficha.style.setProperty("--c", COLOR.sin);
    ficha.replaceChildren(el("p", { textContent: `No encontramos "${nombre}". Probá con una ciudad sobre el Paraná o una cuenca del AMBA.` }));
    return;
  }
  ficha.hidden = false;
  if (l.tipo === "puerto") fichaPuerto(ficha, l.p);
  else fichaZona(ficha, l.id, l.z);
  document.getElementById("lugar").value = l.nombre;
  if (desplazar) ficha.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function fichaPuerto(ficha, p) {
  const nivel = p.viejo ? "sin" : p.nivel;
  ficha.className = "ficha";
  ficha.style.setProperty("--c", COLOR[nivel]);
  ficha.replaceChildren(
    escala(p, "escala--grande"),
    el("div", {},
      el("h3", { textContent: p.puerto }),
      el("p", { className: "ficha-estado", textContent: p.viejo ? "Sin lectura reciente" : NIVEL_TXT[p.nivel] }),
      el("p", { textContent: `El río está en ${m(p.altura)}. ${fraseNivel(p)}` }),
      el("p", { textContent: fraseTendencia(p) }),
      el("p", { className: "ficha-pie", textContent: `Lectura de la escala de Prefectura del ${cuando(p.ts)}.`
        + (p.nivel === "evacuacion" ? " Si vivís cerca del río, seguí las indicaciones de Defensa Civil de tu municipio." : "") })));
  seleccionarParada(p.puerto, { volar: true });
}

function fichaZona(ficha, id, z) {
  ficha.className = "ficha ficha-zona";
  ficha.style.setProperty("--c", COLOR[z.nivel_smn]);
  const partes = [el("h3", { textContent: z.nombre }), el("p", { className: "ficha-estado", textContent: SMN_TXT[z.nivel_smn] })];
  for (const a of z.alertas.slice(0, 2)) {
    partes.push(el("p", { textContent: `${SMN_TXT[a.nivel]} por ${a.evento.toLowerCase()} hasta el ${cuando(a.expira)}.` }));
    partes.push(el("p", { className: "ficha-pie", textContent: a.descripcion }));
  }
  if (!z.alertas.length) partes.push(el("p", { textContent: "El Servicio Meteorológico no tiene alertas para esta cuenca." }));
  if (id === "costa-delta") {
    const C = resumenCosta();
    if (C.res) partes.push(el("p", { textContent: `En San Fernando el agua está ${distancia(C.res[1])} ${C.res[1] >= 0 ? "más alta" : "más baja"} que la marea de todos los días.` }));
    if (C.delta.length) partes.push(el("p", { textContent: `Escalas del Delta: ${C.delta.map((p) => `${p.puerto} ${NIVEL_TXT[p.nivel].toLowerCase()}`).join(", ")}.` }));
  }
  partes.push(el("p", { className: "ficha-pie", textContent: "Ante una emergencia seguí a Defensa Civil de tu municipio (103)." }));
  ficha.replaceChildren(...partes);
  const capa = capasZona.get(id);
  if (capa) { vista("amba", false); mapa.flyToBounds(capa.getBounds(), { maxZoom: 12, duration: 0.8 }); }
}

// ── 3 · El río: mapa + escalas ordenadas por gravedad ──
const mapa = L.map("mapa", { zoomControl: true, scrollWheelZoom: false }).setView([-31, -60], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 16,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Cuencas: COHIFE, BA Data',
}).addTo(mapa);
const capaPuertos = L.layerGroup().addTo(mapa);
const marcadores = new Map();
const capasZona = new Map();
let capaZonas = null;
let limitesParana = null;
let mapaEncuadrado = false;
const VISTA_AMBA = L.latLngBounds([-34.95, -58.95], [-34.25, -58.2]);

function vista(cual, volar = true) {
  for (const b of document.querySelectorAll(".mapa-vistas button")) b.setAttribute("aria-pressed", String(b.dataset.vista === cual));
  if (!volar) return;
  if (cual === "amba") mapa.flyToBounds(VISTA_AMBA, { duration: 0.8 });
  else if (limitesParana) mapa.flyToBounds(limitesParana, { padding: [24, 24], duration: 0.8 });
}
for (const b of document.querySelectorAll(".mapa-vistas button")) b.addEventListener("click", () => vista(b.dataset.vista));

function pintarMapa() {
  capaPuertos.clearLayers();
  marcadores.clear();
  const pts = [];
  for (const p of datos.parana?.puertos ?? []) {
    if (p.lat == null) continue;
    pts.push([p.lat, p.lon]);
    const nivel = p.viejo ? "sin" : p.nivel;
    const mk = L.circleMarker([p.lat, p.lon], {
      radius: { evacuacion: 9, alerta: 7, normal: 5 }[nivel] ?? 5, weight: 2, color: "#fbf6ee",
      fillColor: HEX[nivel] ?? "#9a8f82", fillOpacity: 1,
    }).bindTooltip(`${p.puerto} · ${p.viejo ? "sin dato" : NIVEL_TXT[p.nivel]} · ${m(p.altura)}`)
      .on("click", () => { seleccionarParada(p.puerto, { desplazar: true }); })
      .addTo(capaPuertos);
    marcadores.set(p.puerto, mk);
  }
  limitesParana = pts.length ? L.latLngBounds(pts) : null;
  if (capaZonas) capaZonas.remove();
  capasZona.clear();
  if (datos.zonas && datos.estado) {
    capaZonas = L.geoJSON(datos.zonas, {
      style: (f) => {
        const n = datos.estado.zonas[f.properties.id]?.nivel_smn ?? "verde";
        return { color: HEX[n], weight: 1.5, fillColor: HEX[n], fillOpacity: n === "verde" ? 0.06 : 0.3 };
      },
      onEachFeature: (f, capa) => {
        capasZona.set(f.properties.id, capa);
        const z = datos.estado.zonas[f.properties.id];
        if (z) capa.bindTooltip(`${z.nombre} · ${SMN_TXT[z.nivel_smn]}`).on("click", () => mostrarLugar(z.nombre));
      },
    }).addTo(mapa);
    capaZonas.bringToBack();
  }
  if (limitesParana && !mapaEncuadrado) { mapa.fitBounds(limitesParana, { padding: [24, 24] }); mapaEncuadrado = true; }
}

function parada(p) {
  const nivel = p.viejo ? "sin" : p.nivel;
  const li = el("li", { className: `parada parada--${p.nivel}`, tabIndex: 0, dataset: { puerto: p.puerto }, style: { "--c": COLOR[nivel] } },
    escala(p),
    el("div", {},
      el("p", { className: "parada-nombre", textContent: p.puerto }),
      el("p", { className: "parada-frase" },
        el("b", { textContent: p.viejo ? "Sin dato reciente" : NIVEL_TXT[p.nivel] }),
        ` · ${m(p.altura)}, ${fraseCorta(p)}${flecha(p)}`)));
  const ir = () => { seleccionarParada(p.puerto, { volar: true }); };
  li.addEventListener("click", ir);
  li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ir(); } });
  return li;
}

function pintarEscalas() {
  const lista = document.getElementById("escalas");
  const ps = [...(datos.parana?.puertos ?? [])].sort(porGravedad);
  const grupos = [
    ["evacuacion", "En evacuación", ps.filter((p) => !p.viejo && p.nivel === "evacuacion")],
    ["alerta", "En alerta", ps.filter((p) => !p.viejo && p.nivel === "alerta")],
    ["normal", "Normal", ps.filter((p) => !p.viejo && p.nivel === "normal")],
    ["sin", "Sin lectura reciente", ps.filter((p) => p.viejo)],
  ];
  const items = [];
  for (const [nivel, titulo, grupo] of grupos) {
    if (!grupo.length) continue;
    items.push(el("li", { className: "grupo-titulo", style: { "--c": COLOR[nivel] }, textContent: `${titulo} · ${grupo.length}` }));
    const ocultos = nivel === "normal" || nivel === "sin" ? grupo.slice(NORMALES_VISIBLES) : [];
    for (const p of grupo) {
      const li = parada(p);
      if (ocultos.includes(p)) li.hidden = true;
      items.push(li);
    }
    if (ocultos.length) {
      const b = el("button", { type: "button", className: "mas", textContent: `Ver los otros ${ocultos.length} puertos` });
      b.addEventListener("click", () => {
        for (const li of lista.querySelectorAll(`.parada--${nivel}[hidden]`)) li.hidden = false;
        b.remove();
      });
      items.push(el("li", {}, b));
    }
  }
  if (!ps.length) items.push(el("li", { className: "parada-frase", textContent: "Todavía no hay alturas del Paraná. Reintentamos en un minuto." }));
  lista.replaceChildren(...items);
}

function seleccionarParada(nombre, { volar = false, desplazar = false } = {}) {
  for (const li of document.querySelectorAll(".parada")) li.setAttribute("aria-current", String(li.dataset.puerto === nombre));
  const li = document.querySelector(`.parada[data-puerto="${CSS.escape(nombre)}"]`);
  if (li?.hidden) li.hidden = false;
  if (desplazar && li) li.scrollIntoView({ behavior: "smooth", block: "nearest" });
  const mk = marcadores.get(nombre);
  if (volar && mk) { vista("parana", false); mapa.flyTo(mk.getLatLng(), 9, { duration: 0.8 }); mk.openTooltip(); }
}

// ── Detalle técnico ──
let estSud = "SFER";
function pintarDetalle() {
  const est = datos.serie?.estaciones?.[estSud];
  if (est && window.Grafico) {
    Grafico.dibujar(document.getElementById("grafico"), est, estSud === "SFER" ? datos.serie.pronostico_sfer : [],
      new Date(datos.serie.generado).getTime());
  }
  document.getElementById("sud-est").textContent = { SFER: "San Fernando", BSAS: "Buenos Aires", LPLA: "La Plata" }[estSud];
  const LLUVIA = { sin: "Sin lluvia", debil: "Lluvia débil", moderada: "Lluvia moderada", fuerte: "Lluvia fuerte" };
  const meteo = (datos.estado?.estaciones ?? []).filter((s) => s.tipo === "meteo");
  document.getElementById("lluvia").replaceChildren(...meteo.map((s) => el("li", {},
    el("span", { textContent: s.nombre }), el("span", { textContent: s.viejo ? "sin dato" : LLUVIA[s.lluvia ?? "sin"] }))));
  const fuentes = Object.entries(datos.estado?.fuentes ?? {});
  if (datos.parana) fuentes.push([`Paraná: ${datos.parana.fuente}`, { ok: true }]);
  document.getElementById("fuentes").replaceChildren(...fuentes.map(([n, f]) => el("li", {},
    el("span", { textContent: n }), el("span", { textContent: f.ok ? "ok" : "sin respuesta" }))));
  if (datos.estado) document.getElementById("actualizado").textContent = `Datos actualizados el ${cuando(datos.estado.generado)}.`;
}
for (const b of document.querySelectorAll(".sud-tabs button")) {
  b.addEventListener("click", () => {
    estSud = b.dataset.est;
    for (const x of document.querySelectorAll(".sud-tabs button")) x.setAttribute("aria-pressed", String(x === b));
    pintarDetalle();
  });
}

// ── Navegación por pasos: marca el paso visible ──
const pasos = new Map([...document.querySelectorAll(".pasos a")].map((a) => [a.dataset.paso, a]));
new IntersectionObserver((entradas) => {
  for (const e of entradas) {
    if (!e.isIntersecting) continue;
    for (const [id, a] of pasos) a.setAttribute("aria-current", String(id === e.target.id));
  }
}, { rootMargin: "-45% 0px -50% 0px" }).observe(document.getElementById("hoy"));
for (const id of ["tu-lugar", "rio", "avisar"]) {
  new IntersectionObserver((entradas) => {
    for (const e of entradas) if (e.isIntersecting) for (const [k, a] of pasos) a.setAttribute("aria-current", String(k === id));
  }, { rootMargin: "-45% 0px -50% 0px" }).observe(document.getElementById(id));
}

// ── Buscador ──
const input = document.getElementById("lugar");
input.addEventListener("change", () => { if (input.value.trim()) mostrarLugar(input.value); });
input.addEventListener("keydown", (e) => { if (e.key === "Enter" && input.value.trim()) mostrarLugar(input.value); });

// ── Carga ──
async function refrescar() {
  const [parana, estado, serie, zonas] = await Promise.allSettled([
    cargar("data/parana.json"), cargar("data/estado.json"), cargar("data/serie.json"),
    datos.zonas ? Promise.resolve(datos.zonas) : cargar("data/zonas.geojson"),
  ]);
  // Un archivo con otra versión de esquema se ignora: mejor "sin datos" que datos mal leídos.
  const valido = (r, clave) => {
    if (r.status !== "fulfilled") return false;
    if (r.value?.version === VERSIONES[clave]) return true;
    console.warn(`${clave}.json: versión ${r.value?.version}, la página espera ${VERSIONES[clave]}`);
    return false;
  };
  if (valido(parana, "parana")) datos.parana = parana.value;
  if (valido(estado, "estado")) datos.estado = estado.value;
  if (valido(serie, "serie")) datos.serie = serie.value;
  if (zonas.status === "fulfilled") datos.zonas = zonas.value;
  pintarHoy();
  pintarBuscador();
  pintarEscalas();
  pintarMapa();
  pintarDetalle();
}
refrescar();
setInterval(refrescar, 5 * 60_000);
