# Publicaciones para redes

En cada poll, `alertas/publicar/` arma una publicación para Instagram con el estado del día:
un carrusel de 3 imágenes de 1080×1350 (portada, puertos del Paraná más afectados, costa y
tormentas) y el texto. Se revisa en `/publicaciones.html`.

**Modo prueba:** por ahora no se publica nada en ningún lado. La página muestra si la
publicación saldría y por qué.

## Cuándo se publicaría

| Regla | Detalle |
|---|---|
| Resumen diario | En la primera corrida desde las 8 (hora argentina) |
| Cambio importante | Un puerto entra o sale del nivel de evacuación, o el SMN emite una alerta naranja o roja nueva para una cuenca del AMBA |
| Tope | Nunca más de 4 publicaciones por día |
| Fuente caída | Si Prefectura/INA o el SMN no responden, no se toma como "todo volvió a la normalidad" |

Toda publicación lleva "No es un sistema oficial" y el 103 de Defensa Civil.

La memoria entre corridas (qué se vio y qué se publicó) está en `data/publicaciones.json`
y se conserva con el caché de GitHub Actions.

## Tipografías

`alertas/tipografias/`: Archivo (Omnibus-Type) e IBM Plex Mono, bajo licencia SIL Open Font
License (ver `OFL.txt`), las mismas de la web.
