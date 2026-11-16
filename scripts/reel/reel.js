// Recorrido automático para grabar el reel. Tiempos = segundos del audio de Julieta.
(() => {
  const ESPERA_INICIAL = 4000; // pantalla negra para que cargue todo y para detectar el arranque
  const SUBS = [
    [0.0, 3.1, "Hoy 8 ciudades del Paraná están en evacuación"],
    [3.1, 6.6, "desde Goya hasta Diamante. Otras 4, en alerta."],
    [6.6, 9.5, "En Buenos Aires y el Delta, el río está tranquilo."],
    [9.5, 10.5, "¿Y en tu ciudad?"],
    [10.5, 14.2, "En Santa Fe, el río pasó por 7 cm el nivel de evacuación."],
    [14.2, 17.8, "Acá está todo el Paraná, de lo más grave a lo más tranquilo."],
    [17.8, 19.4, "No somos un sistema oficial."],
    [19.4, 22.6, "Ante una emergencia: Defensa Civil, 103."],
  ];

  const css = document.createElement("style");
  css.textContent = `
    html { scroll-behavior: auto !important; }
    ::-webkit-scrollbar { display: none; }
    #reel-negro { position: fixed; inset: 0; background: #000; z-index: 99999; transition: opacity .25s; }
    #reel-sub { position: fixed; left: 14px; right: 14px; bottom: 56px; z-index: 99998; text-align: center;
      font: 800 24px/1.22 Archivo, system-ui, sans-serif; color: #fff; opacity: 0; transition: opacity .15s; pointer-events: none; }
    #reel-sub span { background: rgba(8, 20, 34, .86); padding: 6px 12px; border-radius: 10px;
      -webkit-box-decoration-break: clone; box-decoration-break: clone; }
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
  fin.innerHTML = `<b>Alerta Cuencas</b><span class="ig">Seguí a @alertacuencas</span><small>alertacuencas.github.io</small>`;
  document.body.append(negro, sub, fin);

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
    [6.4, () => { const c = costa(); desplazar(y(c, 160), 1100); setTimeout(() => foco(c, 2600), 900); }],
    [9.4, () => desplazar(y("#tu-lugar", 20), 900)],
    [10.4, () => {
      const ms = escribir("Santa Fe");
      setTimeout(() => { mostrarLugar("Santa Fe", { desplazar: false }); desplazar(y("#ficha", 220), 900); foco($("#ficha"), 2400); }, ms + 150);
    }],
    [14.1, () => desplazar(y("#rio", 10), 900)],
    [15.3, () => desplazar(y("#escalas", 120) + 520, 2400)],
    [17.7, () => { const n = $(".no-oficial"); desplazar(y(n, 260), 1000); setTimeout(() => foco(n, 4200), 900); }],
    [22.5, () => { fin.style.opacity = "1"; sub.style.opacity = "0"; }],
  ];

  function arrancar() {
    negro.style.opacity = "0";
    const t0 = performance.now();
    for (const [t, f] of PASOS) setTimeout(f, t * 1000);
    const subs = () => {
      const t = (performance.now() - t0) / 1000;
      const s = SUBS.find(([a, b]) => t >= a && t < b);
      if (s && t < 22.5) {
        if (sub.dataset.t !== s[2]) { sub.innerHTML = `<span>${s[2]}</span>`; sub.dataset.t = s[2]; }
        sub.style.opacity = "1";
      } else sub.style.opacity = "0";
      if (t < 26) requestAnimationFrame(subs);
    };
    requestAnimationFrame(subs);
  }

  addEventListener("load", () => setTimeout(arrancar, ESPERA_INICIAL));
})();
