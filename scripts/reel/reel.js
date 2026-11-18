// Recorrido automático para grabar el reel. Tiempos = segundos del audio de Julieta.
(() => {
  const ESPERA_INICIAL = 4000; // pantalla negra para que cargue todo y para detectar el arranque
  // Lo que cambia cada día viene de reel-dia.js (window.REEL): ciudad, subtítulos y tiempos.
  // T = segundo del audio en que arranca cada bloque del guion.
  const { CIUDAD, SUBS, T } = window.REEL;

  const css = document.createElement("style");
  css.textContent = `
    html { scroll-behavior: auto !important; }
    ::-webkit-scrollbar { display: none; }
    #reel-negro { position: fixed; inset: 0; background: #000; z-index: 99999; transition: opacity .25s; }
    /* Zona segura de Reels: Instagram tapa ~400 px de abajo (cuenta, texto, botones) y ~220 px de arriba.
       La ventana es de 360×640 px CSS y el video final es ×3: bottom 135 → 405 px. */
    #reel-sub { position: fixed; left: 14px; right: 14px; bottom: 135px; z-index: 99998; text-align: center;
      font: 800 24px/1.22 Archivo, system-ui, sans-serif; color: #fff; opacity: 0; transition: opacity .15s; pointer-events: none; }
    #reel-sub span { background: rgba(8, 20, 34, .86); padding: 6px 12px; border-radius: 10px;
      -webkit-box-decoration-break: clone; box-decoration-break: clone; }
    #reel-url { position: fixed; left: 0; right: 0; top: 82px; z-index: 99996; padding: 5px 0; text-align: center;
      background: rgba(11, 34, 54, .92); color: #7fd3ff; font: 600 15px "IBM Plex Mono", monospace; pointer-events: none; }
    #reel-fin { position: fixed; inset: 0; z-index: 99997; display: grid; place-content: center; gap: 14px; text-align: center;
      background: #0b2236; color: #fff; opacity: 0; transition: opacity .5s; font-family: Archivo, system-ui, sans-serif; }
    #reel-fin b { font-size: 40px; font-weight: 900; letter-spacing: -.01em; }
    #reel-fin .ig { font-size: 28px; font-weight: 800; color: #7fd3ff; }
    #reel-fin small { font: 600 17px "IBM Plex Mono", monospace; opacity: .8; }
    .reel-foco { outline: 4px solid #7fd3ff !important; outline-offset: 6px; border-radius: 6px; transition: outline-color .3s; }
  `;
  document.head.append(css);
  const negro = Object.assign(document.createElement("div"), { id: "reel-negro" });
  const sub = Object.assign(document.createElement("div"), { id: "reel-sub" });
  const fin = Object.assign(document.createElement("div"), { id: "reel-fin" });
  const url = Object.assign(document.createElement("div"), { id: "reel-url", textContent: "alertacuencas.github.io" });
  fin.innerHTML = `<b>Alerta Cuencas</b><span class="ig">Seguí a @alertacuencas</span><small>alertacuencas.github.io</small>`;
  document.body.append(negro, sub, url, fin);

  const $ = (s) => document.querySelector(s);
  const y = (sel, margen = 70) => {
    const e = typeof sel === "string" ? $(sel) : sel;
    return e ? e.getBoundingClientRect().top + scrollY - margen : scrollY;
  };
  const suave = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  function desplazar(destino, ms) {
    const desde = scrollY, t0 = performance.now();
    return new Promise((ok) => {
      const paso = (ahora) => {
        const k = Math.min(1, (ahora - t0) / ms);
        scrollTo(0, desde + (destino - desde) * suave(k));
        k < 1 ? requestAnimationFrame(paso) : ok();
      };
      requestAnimationFrame(paso);
    });
  }
  function foco(e, ms) {
    if (!e) return;
    e.classList.add("reel-foco");
    setTimeout(() => e.classList.remove("reel-foco"), ms);
  }
  function escribir(texto) {
    const input = $("#lugar");
    input.focus();
    input.value = "";
    [...texto].forEach((c, i) => setTimeout(() => { input.value += c; }, i * 90));
    return texto.length * 90;
  }

  const costa = () => { const c = $("#carteles"); return c?.children[c.children.length - 2]; };
  const PASOS = [
    [0.0, () => scrollTo(0, 0)],
    [1.2, () => desplazar(y("#carteles", 150), 1800)],
    [T.costa - 0.2, () => { const c = costa(); desplazar(y(c, 160), 1100); setTimeout(() => foco(c, 2600), 900); }],
    [T.tuCiudad - 0.1, () => desplazar(y("#tu-lugar", 20), 900)],
    [T.ciudad - 0.1, () => {
      const ms = escribir(CIUDAD);
      setTimeout(() => { mostrarLugar(CIUDAD, { desplazar: false }); desplazar(y("#ficha", 125), 900); foco($("#ficha"), 2400); }, ms + 150);
    }],
    [T.rio - 0.1, () => desplazar(y("#rio", 10), 900)],
    [T.rio + 1.1, () => desplazar(y("#escalas", 120) + 520, 2400)],
    [T.noOficial - 0.1, () => { const n = $(".no-oficial"); desplazar(y(n, 260), 1000); setTimeout(() => foco(n, 4200), 900); }],
    [T.fin - 0.1, () => { fin.style.opacity = "1"; sub.style.opacity = "0"; }],
  ];

  function arrancar() {
    negro.style.opacity = "0";
    const t0 = performance.now();
    // un bloque que no está en el guion del día (p. ej. la costa) no tiene tiempo: ese paso no se hace
    for (const [t, f] of PASOS) if (Number.isFinite(t)) setTimeout(f, t * 1000);
    const subs = () => {
      const t = (performance.now() - t0) / 1000;
      const s = SUBS.find(([a, b]) => t >= a && t < b);
      if (s && t < T.fin - 0.1) {
        if (sub.dataset.t !== s[2]) { sub.innerHTML = `<span>${s[2]}</span>`; sub.dataset.t = s[2]; }
        sub.style.opacity = "1";
      } else sub.style.opacity = "0";
      if (t < T.fin + 4) requestAnimationFrame(subs);
    };
    requestAnimationFrame(subs);
  }

  addEventListener("load", () => setTimeout(arrancar, ESPERA_INICIAL));
})();
