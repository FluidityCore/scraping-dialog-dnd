# AGENTS.md — Contexto completo de la sesión de construcción

Este documento registra todo lo que se investigó, decidió e implementó durante
la sesión de desarrollo del scraper. Sirve como memoria técnica para retomar el
proyecto en cualquier momento.

---

## Objetivo

Extraer todas las transcripciones de la wiki de Critical Role
(`https://criticalrole.fandom.com/wiki/Transcripts`) organizadas por Campaña,
Arco y Episodio, guardarlas en disco como archivos `.txt` y versionar el
proceso en GitHub de forma incremental (un commit por paso lógico).

---

## Decisiones de arquitectura

### Por qué la MediaWiki API en lugar de scraping HTML directo

El primer intento usó `requests` sobre las URLs normales del wiki
(`https://criticalrole.fandom.com/wiki/Transcripts`). Fandom devolvió **HTTP
403** para todos los requests, incluso con User-Agent de navegador.

Solución: usar el endpoint público de la MediaWiki API:
```
https://criticalrole.fandom.com/api.php?action=parse&page=<TÍTULO>&prop=text&format=json
```
Este endpoint no requiere autenticación, devuelve el HTML renderizado de
cualquier página y no aplica las mismas restricciones que el HTML navegable.

Parámetros clave del API call (en `scraper/client.py`):
- `action=parse` — renderiza la página completa
- `prop=text` — solo el HTML del contenido
- `format=json` — respuesta JSON
- `disablelimitreport=1` — elimina metadatos innecesarios
- `redirects=1` — **crítico**: sigue redirects de MediaWiki automáticamente

### Por qué `redirects=1` es necesario

Varias páginas del wiki tienen títulos que apuntan a redirects internos:
- `The_Endless_Atheneeum/Transcript` → redirige a `The Endless Atheneum (episode)/Transcript`
- `The_Search_for_Grog/Transcript` → redirige a `The Search For Grog/Transcript`
- `The_Mighty_Nein_Reunited_Part_1/Transcript` → redirige a `Part 1 - Unfinished Business/Transcript`

Sin `redirects=1` la API devuelve el HTML de la página de redirect (un div
`.redirectMsg`) en lugar del contenido real. El extractor obtiene texto vacío y
el episodio va al log de faltantes.

### Estructura modular

```
scraper/
  client.py     — HTTP: sesión, fetch con reintentos, conversión URL→título de página
  navigator.py  — Parseo del índice: detecta Campaña / Arco / Episodios
  extractor.py  — Limpieza de HTML de transcripción → texto plano de diálogo
  organizer.py  — I/O de archivos: construye árbol de directorios, escribe log
main.py         — CLI: orquesta todo, maneja flags, logging
```

Cada módulo tiene una responsabilidad única. Esto permite testear y reemplazar
partes sin tocar el resto.

---

## Problemas encontrados y cómo se resolvieron

### 1. HTTP 403 de Fandom

**Síntoma:** Todos los requests a URLs normales del wiki devolvían 403.  
**Diagnóstico:** Fandom bloquea scraping HTML pero deja el API público.  
**Solución:** Cambiar a `api.php?action=parse` en `client.py`. Commit: step 8.

### 2. La wiki tiene tres layouts distintos en la página índice

Al inspeccionar el HTML real de `Transcripts`, se descubrieron tres estructuras
distintas para organizar los episodios:

**Layout A — Campañas 1 y 2:**
```html
<h2>Campaign 1: Vox Machina</h2>
<div class="mw-collapsible">          <!-- un div por arco -->
  <h3>Arc 1: Kraghammer...</h3>
  <div class="mw-collapsible-content">
    <ul><li>episodio + enlace Transcript</li></ul>
  </div>
</div>
```

**Layout B — Campaign Three (Bells Hells):**
```html
<div class="mw-collapsible">          <!-- UN solo div para TODA la campaña -->
  <h2>Campaign Three: Bells Hells</h2>
  <div class="mw-collapsible-content">
    <h3>Arc 1: Jrusar</h3>            <!-- h3 + ul intercalados, sin wrapper -->
    <ul><li>episodio + enlace</li></ul>
    <h3>Arc 2: Ruidus Rising</h3>
    <ul>...</ul>
  </div>
</div>
```

**Layout C — Campaign Four:**
```html
<h2>Campaign Four</h2>
<h3>Arc 1: Overture</h3>             <!-- h3 y ul como hijos directos -->
<ul><li>episodio + enlace</li></ul>
```

El parser original solo manejaba Layout C y Layout A parcialmente. Se reescribió
`navigator.py` con una función recursiva `_process_collapsible()` que detecta
cuál de los tres patrones aplica mirando qué hay dentro del
`mw-collapsible-content`:
- Sub-collapsibles → wrapper de sección (Exandria Unlimited, Miscellaneous)
- `<h3>` directos → wrapper de campaña con arcos inline (Layout B)
- `<ul>` directos → wrapper de arco con episodios (Layout A)

### 3. Episodios con "empty content" en el log

**Síntoma:** 4 episodios en `missing_transcripts.log` con `— empty content (URL)`.  
**Diagnóstico:** Sus páginas de wiki son redirects internos. La API sin
`redirects=1` devuelve el HTML del redirect, que no contiene transcripción.  
**Solución:** Añadir `"redirects": "1"` a los parámetros del API call.

### 4. Episodios sin URL en el índice

3 episodios (`November 2015 Critmas`, `December 2015 Critmas`,
`Critical Role's 'The Dating Game' Panel – SDCC 2016`) no tienen enlace a
transcripción en la página índice del wiki. No existen como subpáginas. No
tienen solución técnica — son genuinamente inexistentes en el wiki.

---

## Estructura de datos producida

```
Output/
  Campaña_Campaign_1__Vox_Machina/
    Arco_Arc_1__Kraghammer_and_Vasselheim/
      001_Arrival_at_Kraghammer_Transcript.txt
      002_Into_the_Greyspine_Mines_Transcript.txt
      ...
    Arco_Arc_2__The_Briarwoods/
      001_The_Feast_Transcript.txt
      ...
  Campaña_Campaign_2__The_Mighty_Nein/
    ...
  Campaña_Campaign_Three__Bells_Hells/
    Arco_Arc_1__Jrusar/
      001_The_Draw_of_Destiny_Transcript.txt
      ...
  Campaña_Campaign_Four/
    Arco_Arc_1__Overture/
    Arco_Specials/           ← los one-shots y especiales van aquí
  Campaña_Exandria_Unlimited/
    Arco_Exandria_Unlimited_Prime/
    Arco_Exandria_Unlimited__Kymal/
    ...
  Campaña_Miscellaneous/
    Arco_Candela_Obscura/
    Arco_Age_of_Umbra/
    ...
  missing_transcripts.log
```

Cada archivo `.txt` tiene un header autocontenido:
```
Campaign : Campaign 1: Vox Machina
Arc      : Arc 1: Kraghammer and Vasselheim
Episode  : Arrival at Kraghammer
============================================================

MATT: Hello everyone, and welcome to Critical Role...
```

---

## Volumen de datos

| Sección | Arcos | Episodios |
|---------|-------|-----------|
| Campaign 1: Vox Machina | 5 | 115 |
| Campaign 2: The Mighty Nein | 6 | 141 |
| Campaign Three: Bells Hells | 6 | 121 |
| Campaign Four | 4 | 25 |
| Exandria Unlimited | 4 | 18 |
| Specials | 1 | 99 |
| Miscellaneous | 9 | 41 |
| **Total** | **35** | **560** |

(563 detectados en el índice, 3 sin URL disponible en el wiki)

---

## Commits del repositorio

| SHA | Mensaje | Qué resuelve |
|-----|---------|--------------|
| `539d105` | step 1: project scaffold | `.gitignore`, `requirements.txt` |
| `251aabd` | step 2: HTTP client | Módulo de fetch con reintentos y delay |
| `6924605` | step 3: index navigator | Parser base del índice |
| `ab01a11` | step 4: transcript extractor | Limpieza de HTML → texto |
| `4fc189b` | step 5: file organizer | Árbol de directorios y log |
| `d67a0c9` | step 6: main entry point | CLI, `--dry-run`, `--campaign` |
| `546043b` | step 7: README | Documentación inicial |
| `ae52803` | step 8: fix 403 + parse all campaigns | API client + parser recursivo |
| `1fa2223` | fix: redirects=1 | Páginas de wiki con redirect interno |
| `a0e2c5a` | feat: --skip-existing | Retomar scrapes interrumpidos / reintentar faltantes |

---

## Comandos de uso frecuente

```powershell
# Ver estructura sin descargar nada
py main.py --dry-run

# Solo Campaign 1 (útil para probar)
py main.py --campaign "Campaign 1"

# Scrape completo (~20 min con delay de cortesía de 1-2 s por petición)
py main.py

# Retomar una descarga interrumpida O reintentar los faltantes
py main.py --skip-existing

# Retomar solo una campaña específica
py main.py --campaign "Campaign Three" --skip-existing
```

---

## Limitaciones conocidas y posibles mejoras futuras

| Limitación | Posible mejora |
|------------|----------------|
| Los títulos de episodio incluyen comillas y espacios del wiki | Normalizar con regex más agresivo en `organizer._slugify` |
| `arc_ep_num` reinicia en 1 por sección, no es global | Pasar un contador global si se necesita numeración absoluta |
| Specials aparece como arco dentro de "Campaign Four" | Añadir lógica para promover collapsibles con heading no-"Arc" a campaña propia |
| No verifica si el archivo existente está completo/corrupto | Añadir checksum o verificar tamaño mínimo antes de saltar con `--skip-existing` |
| Si el wiki cambia su estructura HTML, el parser falla silenciosamente | Añadir assertions o alertas cuando `sections` queda vacío por campaña |
