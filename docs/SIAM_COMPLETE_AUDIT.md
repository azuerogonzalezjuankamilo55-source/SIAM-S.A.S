# SIAM 2.0 — Auditoría Integral

> Fecha: 2026-08-14 · Alcance: todo el repositorio (código, plantillas, tests, migraciones, deploy)
> Principios aplicados: **no eliminar/duplicar funcionalidad existente**, no cambios destructivos, reutilizar antes de crear, suite de tests siempre en verde.

---

## 1. Inventario verificado (números exactos)

| Componente | Cantidad | Detalle |
|---|---|---|
| Rutas HTTP | **150** | 144 en 21 blueprints (`routes/*.py`) + 6 a nivel de app (`app.py`: `/`, `/health`, `/robots.txt`, `/sitemap.xml`, `/manifest.json`, `/favicon.ico`) |
| Blueprints | 21 | auth, portal, citas, clientes, vehiculos, mecanicos, ordenes_trabajo, facturas, cotizaciones, garantias, inventario, dashboard, historial, recordatorios, sedes, asistentes, servicios, reportes, configuracion, notificaciones, descargas |
| Plantillas | **83** | Todas renderizadas (0 huérfanas): 76 páginas + `base.html` (layout) + 6 includes `partials/*` + 11 includes `configuracion/_*.html` |
| Modelos | **27** | `models/*.py` (sin `__init__`) |
| Servicios | **18** | `services/*.py` (sin `__init__`), incluye `vehiculo_service.py` nuevo |
| Formularios | **13** | `forms/*.py` (sin `__init__`) |
| Tests | **29** archivos → **377** pruebas (376 passed, 1 skip) |
| Migraciones | **15** | Cadena lineal `001→…→b5d7e9a2c1f6` (HEAD, 1 raíz, sin heads múltiples) |
| Archivos estáticos | 1 CSS + 2 JS + 9 dependencias CDN (sin SRI) | `static/` |

## 2. Duplicados detectados

### 2.1 Resueltos en esta auditoría
| Duplicado | Dónde | Acción |
|---|---|---|
| Endpoint `obtener-vehiculos/<cliente_id>` idéntico ×4 | `routes/citas.py`, `routes/ordenes_trabajo.py`, `routes/cotizaciones.py`, `routes/garantias.py` | Consolidado en `services/vehiculo_service.py:VehiculoService.listar_para_select()`; las 4 rutas ahora lo delegan (misma respuesta JSON, 0 cambio de comportamiento) |
| Catálogo de mantenimiento triplicado con **divergencia real** en rotación de llantas (10 000 vs 40 000 km) | `historial_service.INTERVALOS_MANTENIMIENTO` (canónico: 40 000) vs `inteligencia_service.py:254` (10 000) vs `assistant_service.py` (10 000) | Textos corregidos a **40 000 km** (rotación) y **15 000 km** (frenos) para coincidir con el catálogo canónico |

### 2.2 Documentados, conservados a propósito (compatibilidad)
| Duplicado | Decisión |
|---|---|
| Panel de configuración dual: `routes/facturas.py` (`/facturas/configuracion`) vs `routes/configuracion.py` (FASE 15) | Ambos se conservan. El panel FASE 15 es el canónico (único enlace del sidebar). La ruta legacy se mantiene 200 OK porque `test_audit.py:115` y `test_fase15_configuracion.py` dependen de ella. **Sugerencia P2**: convertir la legacy en redirect al panel nuevo y actualizar los tests |
| `facturas/ver.html` vs `portal/factura_detalle.html` (~60 % solapado) | No son copias exactas: la vista portal es un subconjunto solo-lectura. Se mantiene tal cual (permitido por diseño) |
| `ESTADOS_OT` en `models/orden_trabajo.py` (lista de strings) y `forms/orden_trabajo_forms.py` (lista de tuples) | Estructuras distintas con distintos consumidores y tests que las validan. Consolidar rompería `test_fase4_ordenes.py`; se documenta sin tocar |
| `NIVELES_COMBUSTIBLE` en form y service | Iguales en contenido; sin impacto funcional |
| `DashboardService` vs `ReporteService` (cálculo de ingresos/ticket) | **Resuelto en fase de consolidación**: `cartera()`, `ingresos()` e `ingresos_por_metodo()` ahora son canónicos en `ReporteService`; `DashboardService` delega (mismos valores, 0 cambio de comportamiento). `ticket_promedio` quedó documentado con definiciones intencionalmente distintas (dashboard: total no anulado/nº facturas; reportes: solo pagado+parcial) — no se unificó para no alterar métricas visibles. *Nota: la auditoría inicial afirmó por error que `PortalService` recalcula ingresos; verificado: no lo hace, por lo que no se tocó* |
| Recordatorio por reposición vs mantenimiento (ambos crean `Recordatorio`) | Flujos intencionalmente distintos (`tipo="inventario"` vs `"mantenimiento"`); se unifica el *fechado* vía `_dias_anticipacion()` |
| Numeración de OT | Calculada en dos sitios (modelo y service); consistente, sin drift verificado |

### 2.3 Código muerto detectado (no eliminado: cambios no destructivos)
Métodos sin llamadas en producción (`grep`): `get_iva_rate`, `get_orden_trabajo_servicios`, `get_para_vehiculo` (×2), `marcar_vencidas`, `SedeService.get`. **P3**: retirar tras confirmar con el equipo (algunos son usados por tests, por lo que su borrado exige actualizar tests).

## 3. Errores corregidos (FASE C)
| Error | Archivo | Fix |
|---|---|---|
| Intervalo de rotación de neumáticos inconsistente (10 000 vs 40 000 km) | `services/inteligencia_service.py:254` | → "Cada 40,000 km para desgaste parejo" |
| Idem en el asistente (textos al cliente) | `services/assistant_service.py` (líneas 836, 841, 856, 1207, 1209) | Frenos → 15 000 km, Rotación → 40 000 km (acordes al catálogo canónico) |
| **Crítico deploy**: `migrations/versions/` excluido de git → las migraciones no se despliegan a Neon | `.gitignore:38` | Eliminada la línea; el directorio ya aparece como untracked (`git status`) |
| Conexión `notif_recordatorio_dias` sin test | `tests/test_fase15_configuracion.py` | Añadidos 2 tests (`_dias_anticipacion` usa config; `generar_mantenimientos` respeta la anticipación) |

## 4. Seguridad (FASE F) — estado verificado
| Área | Estado |
|---|---|
| CSP estricta (`default-src 'self'`, sin `unsafe-inline`, sin `unsafe-eval` en script-src) | ✅ Aplicada en `app.py` |
| HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy | ✅ Aplicadas |
| CSRF (Flask-WTF) en todos los formularios | ✅ |
| `staff_blueprint_guard` protege blueprints de staff | ✅ |
| `ProductionConfig.validate()` falla rápido si falta `SECRET_KEY`/`DATABASE_URL` | ✅ |
| Rate limiting (Flask-Limiter) | ✅ |
| `prefers-reduced-motion` en CSS/landing/sedes/asistente | ✅ |
| Credenciales en repo | ⚠️ `.env` está en `.gitignore` y no versionado; `docs/database-production-audit.md:8` documenta el host real de Neon (host ≠ secreto, pero **P2**: rotar contraseña de Neon y no reutilizar el host en docs si se compartirá el repo) |
| `SECRET_KEY` default débil en dev (`config.py`) | ⚠️ Solo afecta dev; prod se valida. **P3**: generar aleatorio en dev |

## 5. Base de datos y deploy (riesgos Render/Neon)
| Riesgo | Severidad | Estado |
|---|---|---|
| Migraciones no versionadas en git | **ALTO** | ✅ Corregido (`.gitignore`) — falta `git add` + commit (no se hizo commit por instrucción) |
| Uploads sin disco persistente en Render (`render.yaml`) | **ALTO** | ⚠️ Documentado; se pierden en cada redeploy. **P1**: volumen de disco (mín. 1 GB) + backup de `uploads/` |
| Health check (`/health`) no valida conexión a BD | **BAJO** | ⚠️ **P2**: añadir `SELECT 1` al endpoint (ya anotado en `PRE_PRODUCTION_CHECKLIST.md`) |
| Pool de conexiones (pool_size × workers) para Neon Free Tier | MEDIA | ⚠️ Documentado en `PRE_PRODUCTION_CHECKLIST.md:267`; `pool_recycle` pendiente de ajuste |
| `runtime.txt` → `python-3.12.3`; `Procfile` → gunicorn 4 workers | OK | Consistentes |
| PDFs WeasyPrint | Skip de test en Windows (dependencia nativa) | OK en Linux/Render |

## 6. Evidencia (FASE G)
```
py -3.14 -m pytest
376 passed, 1 skipped in 116.18s
```
- Antes: 374 passed, 1 skipped · Después: 376 passed, 1 skipped (+2 tests nuevos).
- Skip único: PDF WeasyPrint en Windows (esperado).

## 7. Archivos modificados en esta auditoría
- `services/vehiculo_service.py` (**nuevo**): `listar_para_select()` compartido
- `routes/citas.py`, `routes/ordenes_trabajo.py`, `routes/cotizaciones.py`, `routes/garantias.py`: delegan en el helper
- `services/inteligencia_service.py`, `services/assistant_service.py`: intervalos corregidos
- `services/reporte_service.py`: métodos canónicos `ingresos()`, `cartera()`, `ingresos_por_metodo()`; `build_resumen` los usa
- `services/dashboard_service.py`: delega `ingresos_hoy`, `ingresos_mes`, `por_cobrar` e `ingresos_por_metodo` en `ReporteService`
- `.gitignore`: versionar `migrations/versions/`
- `tests/test_fase15_configuracion.py`: +2 tests

## 8. Pendientes priorizados (siguientes pasos sugeridos)
- **P0**: `git add migrations/versions/` + commit y aplicar `flask db upgrade` en Neon (bloqueado hasta autorización de commit)
- **P1**: disco persistente para uploads en Render (hoy se pierden)
- **P2**: legacy `/facturas/configuracion` → redirect al panel nuevo; `/health` con chequeo de BD; rotar contraseña Neon
- **P3**: retirar código muerto listado; `SECRET_KEY` aleatorio en dev; SRI en dependencias CDN
- **UX (fase abierta)**: calendario visual de citas (grilla) y AJAX en formularios principales — enlace "Configuración del Sistema" ya operativo
