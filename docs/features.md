# Funciones de la plataforma

Contexto para las funciones que vamos sumando a Alerta Cuencas. Las fases están en la
[hoja de ruta del README](../README.md#hoja-de-ruta). El criterio de producto está en la
sección 0 de [`diseno-fase1.md`](diseno-fase1.md), que manda si algo se contradice.

## Principios para cualquier función nueva

- **Sudestada en Costa/Delta y el Paraná** son el foco. La lluvia en CABA queda como tablero.
- **Vocabulario de observación:** describimos lo que miden los organismos y no emitimos alertas propias.
- **Pensado para el celular** de quien vive cerca del agua, en lenguaje claro.
- **Sin servidores propios:** GitHub Actions y GitHub Pages, gratis y funcionando las 24 horas.
- **Siempre visible** el aviso "No es un sistema oficial".
- Tests con `uv run pytest`, que corre sin internet.

## Qué hay hoy

| Función | Dónde | Desde |
|---|---|---|
| Sudestada en vivo (SHN más el pronóstico del INA a 48 h) | web, paso 1 | `350dab7` |
| El Paraná puerto por puerto, con los niveles de Prefectura y respaldo del INA | web, paso 3 | `04af479`, `f2006bd` |
| Mapa y lista ordenados por gravedad | web, paso 3 | `d822a56` |
| Web en cuatro pasos: hoy, tu lugar, el río y avisar | web | `9cb6e4b` |
| Publicaciones para Instagram en modo prueba | `/publicaciones.html` | `5ae3465` |
| Contacto por mensaje directo de Instagram | web | `cd90cb2` |
| Reel diario | [`reels/`](../reels/README.md) | 16/11/2026 |

## Pendientes e ideas

Una fila por función. El estado puede ser idea, diseño, en curso o hecha.

| Función | Para qué | Estado | Notas |
|---|---|---|---|
| Paso 4 "Avisar" | Que la gente reciba el aviso | idea | Hoy dice "próximamente". Por WhatsApp a través de referentes (Fase 2) |
| Avisos de sudestada en modo prueba | Fase 1 | diseño | Bloqueado: hay que confirmar el datum con el SHN |
| Lluvia medida en tiempo real en CABA | Tablero | idea | Falta una fuente |

## Ficha para una función nueva

Cuando una idea pasa a diseño, se le agrega una sección como esta:

```
### <Nombre>
- **Problema:** qué le pasa a quién.
- **Propuesta:** qué hacemos, en una o dos oraciones.
- **Datos o fuentes:** de dónde sale.
- **Cómo sabemos que funciona:** criterio de aceptación.
- **Fuera de alcance:** qué no hace.
```
