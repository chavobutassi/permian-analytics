# Plan de Proyecto — Permian Basin Production Analytics

Gemelo estadounidense de tu proyecto Vaca Muerta. Objetivo doble: **(1)** un dashboard público en inglés sobre producción de la cuenca Permian, y **(2)** evidencia concreta para el EB-2 NIW de que tu trabajo beneficia directamente al sector energético de EE.UU.

**Principio guía:** reutilizar al máximo el molde de Vaca Muerta. No reinventás nada — adaptás fuente de datos y terminología.

**Estrategia de alcance (importante):** arrancá con **datos agregados de la EIA** (nivel cuenca, confiables y limpios) como primera versión funcionando. Recién después, si querés más profundidad, sumás datos por pozo de los reguladores estatales (más ricos pero mucho más sucios). MVP primero, profundidad después.

---

## Fase 0 — Preparación (medio día)

- [ ] Registrar **API key de la EIA** en eia.gov/opendata (gratis, inmediata).
- [ ] Crear repo nuevo en GitHub: `permian-analytics` (público).
- [ ] Clonar la **estructura de carpetas** de `vaca-muerta-analytics` como base.
- [ ] Armar entorno Python (`venv` + `requirements.txt`): pandas, requests, plotly, python-dotenv.
- [ ] Guardar la API key en `.env` (nunca en el código; agregá `.env` al `.gitignore`).

**Entregable:** repo vacío pero con esqueleto y entorno listo.

---

## Fase 1 — Exploración y mapeo de datos (1–2 días)

- [ ] Leer la doc de la **EIA API v2** e identificar las series de la Permian:
  - *Drilling Productivity Report (DPR)*: producción, rig productivity, DUCs, new-well vs legacy por región (incluye Permian).
  - Series de producción de crudo y gas por región/estado.
- [ ] Confirmar los **series IDs / endpoints exactos** que vas a consumir (esto lo hacemos juntos, probando la API en vivo).
- [ ] Decidir el **grano** de la v1: mensual, a nivel cuenca Permian.
- [ ] (Opcional, para v2) Revisar **Texas RRC** y **New Mexico OCD** para datos por pozo.

**Entregable:** un notebook de exploración que trae datos reales de la Permian y un documento corto con "qué series uso y qué columnas tienen".

---

## Fase 2 — Pipeline ETL (2–4 días)

Misma arquitectura que Vaca Muerta: **Extract → Transform → Load.**

- [ ] **Extract:** funciones que llaman la API de la EIA con manejo de errores, paginación y **caché local** (para no repegar la API en cada corrida). Reutilizá tu patrón de fallback/caching de Vaca Muerta y de ARGO.
- [ ] **Transform:** limpiar, normalizar unidades (a **BOE** cuando corresponda) y calcular las métricas:
  - Curva de declinación / producción en el tiempo.
  - GOR = gas / oil.
  - Water cut (si el dato de agua está disponible al nivel elegido).
  - Rig productivity y tendencia de **DUCs**.
  - Uptime/downtime (si aplica al grano de dato).
- [ ] **Load:** guardar el dataset procesado en formato liviano y versionable (Parquet o CSV; opcional SQLite si querés consultas).

**Entregable:** `etl.py` que corre de punta a punta y deja un dataset limpio listo para graficar.

---

## Fase 3 — Capa de analítica (2–3 días)

- [ ] **Curvas de declinación** con **modelo de Arps (hiperbólico)** — tu análisis estrella; portá la lógica desde Vaca Muerta.
- [ ] **Productividad por rig** y evolución del **inventario de DUCs** (relato: "por qué sube la producción aunque bajen los rigs").
- [ ] **Análisis por cohorte/vintage** (si llegás a datos por pozo en v2).
- [ ] **KPIs** de cuenca: producción total, mix oil/gas, tendencias interanuales.

**Entregable:** módulo de análisis con funciones reutilizables + gráficos base.

---

## Fase 4 — Dashboard (2–4 días)

- [ ] Elegir stack de visualización — recomendado **Plotly Dash** (ya lo usaste en ARGO) o Power BI si preferís.
- [ ] Vistas mínimas: overview de cuenca, curvas de declinación, rig productivity + DUCs, y un panel de KPIs.
- [ ] **Todo en inglés** (es un entregable US-facing).
- [ ] Desplegar en vivo (Render, como ARGO, o GitHub Pages si es estático).

**Entregable:** dashboard público con URL viva.

---

## Fase 5 — Automatización / CI-CD (medio día)

- [ ] **GitHub Actions** con refresh **semanal** del ETL (idéntico a Vaca Muerta): corre el pipeline, actualiza datos y redepliega.
- [ ] Badge de estado en el README.

**Entregable:** pipeline que se actualiza solo, sin que lo toques.

---

## Fase 6 — Documentación (medio día) — *acá está el valor NIW*

- [ ] **README en inglés** que explique: qué hace, qué fuentes usa, qué métricas calcula, y **por qué importa para EE.UU.** (independencia energética, transparencia de producción, eficiencia de infraestructura crítica).
- [ ] Capturas del dashboard.
- [ ] Sección "Data sources & methodology" (da seriedad y muestra rigor).

**Entregable:** un repo que cualquiera —incluido un examinador de USCIS— abre y entiende el valor en 30 segundos.

---

## Fase 7 — Enganche con el NIW (integración, no código)

- [ ] Vincular el proyecto a tu *proposed endeavor*: "analítica sobre infraestructura energética de EE.UU.", **ya funcionando**.
- [ ] Sumarlo a tu portfolio y CV como proyecto US-facing.
- [ ] Tenerlo listo para mencionarlo en la reunión del 7 ("acá está, en vivo").

---

## Estimación total

Con tu ritmo y reutilizando Vaca Muerta: **~2 a 3 semanas** de trabajo part-time hasta una v1 pública y automatizada. La v2 con datos por pozo (RRC/OCD) es un esfuerzo aparte, opcional.

## Orden sugerido si tenés poco tiempo

Priorizá **Fases 1 → 2 → 3 (solo curvas de declinación) → 6**. Con eso ya tenés un proyecto presentable. Dashboard bonito (Fase 4) y automatización (Fase 5) los sumás después.

---

*Próximo paso concreto: Fase 1 — explorar juntos la API de la EIA y fijar qué series de la Permian vas a consumir.*
