# SIAM 2.0 — Informe de Duplicación y Consolidación

> Fecha: 2026-08-14 · **Fase de auditoría (sin modificación de código)**
> Método: revisión del 100 % de `services/`, `routes/`, `models/`, `templates/`, `static/js/`, `static/css/`, `app.py`, `tests/`, con verificación individual de cada hallazgo crítico (grep/lectura) antes de reportarlo.
> Evidencia: `376 passed, 1 skipped` · `compileall OK` · 151 endpoints / 231 `url_for` en plantillas / 126 únicos — todos resuelven.

---

## 1. Duplicación de lógica de negocio (services/ + models/)

| # | Archivo:línea (implementación) | Qué hace | Dónde se repite | Fuente única propuesta | Riesgo de eliminarla | Recomendación |
|---|---|---|---|---|---|---|
| 1 | `services/historial_service.py:39-46` `INTERVALOS_MANTENIMIENTO` | Catálogo de mantenimiento preventivo | `models/recordatorio.py:12-28` `TIPOS_MANTENIMIENTO`; textos hardcodeados en `services/inteligencia_service.py:250-256` y `services/assistant_service.py:835` | `INTERVALOS_MANTENIMIENTO` (ya canónico; rotación/frenos alineados en fase anterior) | MEDIO — los textos de IA/asistente se derivarían del catálogo; no hay tests sobre esos textos | Consolidar: IA y asistente leen el catálogo |
| 2 | `models/orden_trabajo.py:17-25` `ESTADOS_OT` | Estados de OT | `forms/orden_trabajo_forms.py:5-13` (tuples) + labels `:76-84` | Modelo | BAJO — tests importan del modelo; el form solo añade labels | Forms importan del modelo (convertir a choices) |
| 3 | `services/orden_trabajo_service.py:16` `NIVELES_COMBUSTIBLE` | Niveles | `forms/orden_trabajo_forms.py:15` (idéntico) | Service | BAJO | El form importa del service |
| 4 | `models/factura.py:11-19` `METODOS_PAGO` | Métodos de pago | labels en `models/pago_factura.py:26-34` (`metodo_pago_display`) | Modelo | BAJO | Unificar labels |
| 5 | `services/factura_service.py:55-78` vs `services/cotizacion_service.py:33-39` | Fórmula total (subtotal + IVA − descuento) | Duplicada en ambos | Helper compartido | MEDIO — cálculos sensibles de dinero | Extraer helper y que ambos lo usen (mismos resultados) |
| 6 | `services/cotizacion_service.py:22-30`, `services/garantia_service.py:18-26`, `routes/ordenes_trabajo.py:32`, `services/factura_service.py:80-82` | Generadores de nº secuenciales (último id + prefijo + pad) | 4 implementaciones | Helper único | BAJO | Extraer helper compartido |
| 7 | `services/portal_service.py:34-50` `get_cliente_de_usuario` | Resolución usuario→cliente | `services/notification_service.py:76`, `routes/auth.py:68` | `PortalService` | BAJO | Unificar |
| 8 | `routes/cotizaciones.py:36-43`, `routes/garantias.py:35-42` `_validar_csrf` + inline en `vehiculos.py:133`, `inventario.py:350`, `clientes.py:82`, `servicios.py:99`, `mecanicos.py:97` | Validación CSRF | ~7 copias | `database/commit.py` | BAJO | Helper único |
| 9 | `services/cotizacion_service.py:183-196`, `services/garantia_service.py:132-145` | Query `get_para_cliente` (filter_by + order created_at desc) | Mismo patrón | Service compartido | BAJO | Consolidar |
| 10 | `services/factura_service.py:32,155`, `services/cotizacion_service.py:191,199`, `services/garantia_service.py:140`, `services/sede_service.py:109` | **Código muerto** (cero callers en routes/services/tests) | — | Eliminar | BAJO (verificado sin callers) | Eliminar tras confirmación (requiere actualizar `docs/SIAM_COMPLETE_AUDIT.md`) |
| — | `services/storage_service.py` vs `services/image_service.py` | Capa de archivos | **NO son duplicados**: `FileService` es general (tipos/mime/tamaño), `ImageService` optimiza imágenes (PIL). `FileService` delega en `ImageService` | — | — | Mantener (complementarios) |

## 2. Duplicación de rutas / páginas

| # | Archivo:línea | Qué hace | Dónde se repite | Fuente única propuesta | Riesgo | Recomendación |
|---|---|---|---|---|---|---|
| 1 | `routes/facturas.py:268` `/facturas/configuracion` + `:317` `quitar_logo` | Configuración de empresa (TallerConfigForm) | `routes/configuracion.py:71` sección empresa + `:275` quitar_logo (misma tabla, mismo form) | Panel FASE 15 (`configuracion/`) | MEDIO — `test_audit.py:115` y `test_fase15:364` esperan 200 en legacy | Redirigir legacy al panel nuevo y actualizar tests |
| 2 | `templates/facturas/ver.html` vs `templates/portal/factura_detalle.html` | Detalle de factura (~50-75 % igual: cabecera, totales, tabla ítems) | Par staff↔cliente | Partial compartido | MEDIO | Extraer partial (patrón ya usado: `facturas/pdf.html` compartido) |
| 3 | `templates/ordenes_trabajo/ver.html` vs `templates/portal/orden_detalle.html` | Detalle de OT (vehículo, mecánico, estado, ítems) | Par staff↔cliente | Partial compartido | MEDIO | Idem |
| 4 | `templates/cotizaciones/ver.html` vs `templates/portal/cotizacion_detalle.html` | Detalle de cotización (ítems + totales) | Par staff↔cliente | Partial compartido | MEDIO | Idem |
| 5 | `templates/citas/form.html:88-92`, `ordenes_trabajo/form.html:82-86`, `garantias/form.html:54-56`, `cotizaciones/form.html:54-58` | Select dependiente cliente→vehículo (fetch idéntico, URL distinta) | 4 inline scripts | Helper en `siam.js` | MEDIO | `initClienteVehiculo(clienteSel, vehiculoSel, url)` |

## 3. Errores funcionales encontrados (verificados)

| # | Archivo:línea | Problema | Severidad |
|---|---|---|---|
| 1 | `templates/sedes.html:106` (`onclick="verSedeEnMapa(...)"`) | La función está dentro del IIFE (`:279`) y solo se expone `window.cancelarAsistencia` (`:383`) → **ReferenceError** al pulsar "Ver en el mapa" | ALTA |
| 2 | `static/js/siam.js` | **No hay handler para `data-confirm-form`**; 7 formularios destructivos lo usan (`cotizaciones/ver.html:128,160,170`, `cotizaciones/listar.html:61`, `portal/cotizacion_detalle.html:69,73`, `garantias/listar.html:56`) → borrar/rechazar/anular se ejecuta **sin confirmación** | ALTA |
| 3 | `templates/portal/documentos.html:47` + `siam.js:121-144` | `data-confirm` sobre un `<form>`; `initDeleteLinks` lee `href` (inexistente en form) → `form.action = "null"` → eliminar documento del portal **no llega a su endpoint** | ALTA |
| 4 | `templates/partials/sidebar.html:107,204` | "Recordatorios" y "Reportes" visibles para todo staff, pero `routes/recordatorios.py` y `routes/reportes.py` son `@admin_required` → `recepcion`/`mecanico` ven enlaces que dan 403 | MEDIA |
| — | `templates/configuracion/_empresa.html:101` | **FALSO POSITIVO descartado**: el botón `disabled` es condicional a `puede_editar` (modo solo lectura para no-editores), no es UI muerta | — |

## 4. Funcionalidades sin uso real en la interfaz (dead endpoints / dead JS)

| # | Elemento | Uso real | Nota |
|---|---|---|---|
| 1 | `routes/citas.py:144` `citas.eliminar` | Ninguno (sin url_for en plantillas) | `test_audit.py` exige 405 en GET → conservar solo como POST o retirar con test |
| 2 | `routes/garantias.py:99,131` `generar_ot`, `generar_servicio` | Solo en `test_fase12_garantias.py` | Sin acceso en UI |
| 3 | `routes/sedes.py:21-23` `sedes.api` | Ninguno + **público sin login** (devuelve sedes/coordenadas) | `test_audit.py:122,139` lo consulta → proteger o retirar actualizando test |
| 4 | `routes/notificaciones.py:62-65` `api_no_leidas` | El polling usa `/api/listar` | Muerto |
| 5 | `static/js/siam.js` `initAjaxDelete`/`data-ajax-delete`, `refreshTable`/`data-ajax-table` | Cero plantillas los usan | JS muerto |
| 6 | `templates/cotizaciones/ver.html:200` `data-otro-mensaje` | Sin handler | Atributo inerte en form visible |

## 5. Separación EMPRESA vs CLIENTE

**Conclusión: correcta en general.** 103 rutas staff (15 blueprints con `staff_blueprint_guard`), 24 cliente (portal con `_portal_guard`, redirige staff a dashboard), 13 ambos (auth.logout, assistant, api, notificaciones — datos scoped por usuario), 10 públicas. El sidebar bifurca por `current_user.es_cliente`.

- **No** hay pantallas administrativas expuestas al cliente.
- Los únicos solapamientos reales son los 3 pares de detalle (factura/OT/cotización) y la pantalla de configuración de empresa (2 implementaciones). Ambos son candidatos a partial único.
- Los blueprints "both" (notificaciones, assistant) mezclan roles a propósito, con datos por usuario: correcto, pero conviene documentarlo (ya anotado).

## 6. Sistema de archivos multimedia

Capacidades verificadas (`services/storage_service.py` `TIPOS_ARCHIVO` + `FileService`):

| Tipo | Soportado | Evidencia |
|---|---|---|
| Fotos (JPG/PNG/WebP) | ✅ | `image_service`, historial/vehículos/OT |
| Videos (MP4) | ✅ (parcial en UI) | `TIPOS_ARCHIVO["video"]`, adjuntos |
| PDF | ✅ | `TIPOS_ARCHIVO["pdf"]`, facturas/portal documentos |
| Documentos | ✅ | portal `adjuntar_documento` (`routes/portal.py:495`) |
| Evidencia de daños/reparación | ⚠️ Parcial | Fotos de historial con `tipo` antes/después (`vehiculos.py:90`) |
| Documentos de garantía | ⚠️ No hay adjunto específico | Gap |

- **Validación**: extensión + MIME + tamaño por variable de entorno (`FILE_MAX_*_MB`) — ✅ en `FileService`.
- **Propietario/permisos**: ✅ portal adjuntos scoped por `current_user` (`AdjuntoService.crear/eliminar`). Rutas de staff protegidas por `staff_blueprint_guard`.
- **Exposición**: ⚠️ los archivos se sirven desde `/static/uploads/` (público por URL). Firmas, cédulas y documentos quedan accesibles con la URL aunque no haya sesión. **Riesgo MEDIO** → servir subcarpetas sensibles por endpoint autenticado o moverlas fuera de `static/`.
- **Duplicación**: capa de archivos no duplicada (`storage`/`image` complementarios). Sí falta centralizar el chequeo de propietario en uploads (hoy por ruta).

## 7. Chat / IA

- **Arquitectura**: detección de intención por regex/keywords con ~30+ intents (lista en `assistant_service.py:30-150`) + flujo de botones + texto libre. **NO es "15 preguntas predeterminadas"**.
- **Cobertura de temas**: todos los solicitados (carros, motos, mantenimiento, fallas, síntomas, repuestos, precios, citas, asistencia, ubicación, OT, garantías) están presentes como intents.
- **Datos reales de BD**: precios de servicios (`:995,1267`), stock y precios de inventario (`:751,770`), sedes (lista real). ✅ No inventa precios ni stock.
- **Datos hardcodeados que podrían quedar desactualizados**:
  - Horario "lunes a viernes 7:00-18:00, sábados 8:00-13:00" (`:875`) — no lee `ConfiguracionTaller`.
  - "Nuestra sede principal está en Soacha" (`:494`) — no lee `Sede`.
  - **Riesgo MEDIO**: si el taller cambia horario/sedes, el asistente responde mal. Recomendación: leer de BD/config.
- **Sin fuzzy matching**: los intents usan coincidencia exacta de keywords normalizadas; una consulta parafraseada puede caer al fallback. Recomendación: sinónimos/normalización avanzada.

## 8. Agenda / citas

| Capacidad | Estado | Evidencia |
|---|---|---|
| Solicitar cita | ✅ | `citas.crear` + `portal.solicitar_cita` |
| Seleccionar vehículo | ✅ | Select dependiente (consolidado en `VehiculoService`) |
| Seleccionar servicio | ✅ | `servicio_id` en form |
| Fecha + hora | ✅ | Form |
| **Hora disponible (grilla de slots)** | ❌ **GAP** | No existe `horas_disponibles(sede, fecha)`. El cliente escribe la hora y el backend valida; no hay picker |
| Estado | ✅ | `cambiar_estado` |
| Confirmación | ⚠️ Parcial | Notificación al crear/editar; sin estado "confirmada" explícito para el cliente |
| Cancelación | ✅ staff / ⚠️ cliente | `cambiar_estado=cancelado`; `citas.eliminar` muerto |
| Notificación | ✅ | `NotificationService.notify_cliente` en crear/editar/estado |
| Evitar horarios ocupados | ✅ | `SedeService.sede_ocupada` en crear/editar/portal (coincidencia exacta; exclusión en editar) |
| Respetar intervalo configurado | ✅ | `ConfiguracionService.hora_en_intervalo` en crear/editar/portal (`citas_intervalo_min`) |
| Race check-then-insert | ⚠️ | Falta índice único parcial `(sede_id, fecha, hora)` para estados activos |

## 9. UX

- **Elementos repetidos**: dicts estado→color/badge (15+ copias), cabeceras de página (38), `data-table-search` (10), fetch dependiente cliente→vehículo (4), scaffold de tarjetas en `configuracion/_*.html` (9).
- **Botones/páginas sin función**: `data-otro-mensaje` (inerte), `citas.eliminar` (muerto), "Ver en el mapa" (roto, §3.1), formularios sin confirmación (§3.2).
- **Animaciones**: AOS se inicializa globalmente en `base.html` (sin chequear `prefers-reduced-motion`); el landing sí lo chequea (`landing.html:799`). `siam.css:1169` respeta reduced-motion. Recomendación: respetar reduced-motion también en la inicialización global de AOS.
- **Responsive**: breakpoints presentes; `siam.css:1129` (767px) y `:1136` (768px) casi duplicados. Sin paginación en listas largas.
- **CDN**: 12 URLs únicas / 20 referencias, **sin SRI ni fallback local** (`base.html:70-75,142-143`; bootstrap, Inter, Font Awesome, AOS). Core CSS/JS local, pero Bootstrap/FA/AOS son CDN → sin ellos la UI se degrada. `landing.html` re-carga el mismo set (7 refs) + GSAP.
- **Recomendación**: SRI o vendorizar, fallback `onerror`, y no depender de CDN para el layout básico.

## 10. Evidencia de verificación

```
py -3.14 -m pytest            → 376 passed, 1 skipped (120 s)
py -3.14 -m compileall ...    → OK (services, routes, models, forms, tests, database, decorators)
url_for (plantillas)          → 151 endpoints en url_map · 231 referencias · 126 únicas · TODAS resuelven
```

## 11. Top 10 de consolidación (orden impacto/riesgo)

| # | Acción | Prioridad | Archivos |
|---|---|---|---|
| 1 | Handler `data-confirm-form` + soporte `data-confirm` en `<form>` en `siam.js` (evita borrados sin confirmación y arregla eliminar documento) | ALTA | `static/js/siam.js`, `portal/documentos.html` |
| 2 | Exponer `verSedeEnMapa` en `window` | ALTA | `templates/sedes.html` |
| 3 | Gate `admin` en sidebar para Recordatorios/Reportes | MEDIA | `templates/partials/sidebar.html` |
| 4 | Consolidar configuración de empresa (2 fuentes → panel FASE 15) + redirect legacy + actualizar tests | MEDIA | `routes/facturas.py`, `routes/configuracion.py`, tests |
| 5 | Macro `badge_estado` (elimina 15+ dicts) | MEDIA | partials + 83 templates |
| 6 | Helper `initClienteVehiculo` en `siam.js` (4 inline) | MEDIA | `siam.js`, 4 forms |
| 7 | Partials compartidos para detalle factura/OT/cotización (staff+cliente) | MEDIA | `templates/*` |
| 8 | Helpers: CSRF único, generadores de nº, constantes desde models, catálogo mantenimiento único | MEDIA | `database/commit.py`, forms, services |
| 9 | Eliminar código muerto (6 métodos) y dead endpoints (actualizando tests que los referencian) | MEDIA | services, routes, tests |
| 10 | CDN con SRI/fallback; AOS respeta reduced-motion; horario/sede del asistente leídos de BD | MEDIA | `base.html`, `assistant_service.py` |

## 12. Decisiones explícitas de NO cambiar (sin evidencia / sin permiso)
- **Métricas existentes** (`ticket_promedio`, ingresos, cartera): comportamiento intacto; no se unifican definiciones distintas sin evidencia.
- **Rutas públicas** (`/`, `/health`, `/sedes/`, `/auth/*`, `/sedes/api`): no se modifican; el retiro de `sedes.api` requiere actualizar `test_audit.py`.
- **Migraciones**: no se generan (ningún cambio de esquema necesario).
- **No se elimina funcionalidad** ni se crean implementaciones paralelas: este informe es previo a cualquier cambio.
