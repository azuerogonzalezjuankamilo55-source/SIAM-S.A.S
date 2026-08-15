# SIAM 2.0 — Roadmap de Implementación

Documento vivo del plan de migración de SIAM hacia un software profesional para talleres
automotrices. Se actualiza al finalizar cada fase.

- **Entorno dev**: Windows (local), `.venv`.
- **Producción**: Render + Neon PostgreSQL (Linux).
- **Regla de oro**: no romper funcionalidad existente; cada fase deja todos los tests en verde.

**Estados usados:**
- ✅ **COMPLETADA** — implementada y verificada por tests.
- 🟡 **PARCIAL** — existe una base, falta funcionalidad importante.
- 🔴 **PENDIENTE** — no iniciada.
- ⚠️ **REQUIERE REVISIÓN** — implementada pero necesita revisión/validación.

**Prioridades:**
- **P0 — crítico** · **P1 — importante** · **P2 — mejora** · **P3 — futuro**

---

## ESTADO ACTUAL DEL PROYECTO

**Tests: `374 passed, 1 skipped`** — la suite completa está **verde**.

- El único skip corresponde al PDF de WeasyPrint en Windows (faltan libs nativas pango/gobject);
  tiene fallback en runtime y debe validarse en Linux/Render.
- Las últimas fases implementadas (Decimal/migraciones, historial/ficha técnica, cotizaciones,
  garantías, notificaciones por rol, panel de configuración) no rompieron ninguna prueba previa.
- Queda documentado en `FINAL_AUDIT.md`, `docs/PRE_PRODUCTION_CHECKLIST.md` y `docs/auditoria.md`
  el estado de auditoría y pre-producción (seguridad, rendimiento, SEO, accesibilidad).

**Módulos activos en producción de código** (blueprints registrados en `app.py`):
`auth`, `dashboard`, `clientes`, `vehiculos`, `servicios`, `mecanicos`, `citas`, `facturas`,
`inventario`, `ordenes_trabajo`, `assistant` (chat IA), `sedes` (mapa/asistencias), `api`
(asistencia por ubicación), `portal` (cliente), `inteligencia` (IA 2.0), `recordatorios`,
`reportes`, `notificaciones`, `cotizaciones`, `garantias`, `configuracion` (panel).

---

## Tabla de fases

| Fase | Descripción | Estado | Tests |
|------|-------------|--------|-------|
| FASE 1 | Decimal/migraciones | ✅ COMPLETADA | suite verde |
| FASE 10 | Historial / ficha técnica | ✅ COMPLETADA | `test_historial.py` |
| FASE 11 | Cotizaciones | ✅ COMPLETADA | `test_fase11_cotizaciones.py` |
| FASE 12 | Garantías | ✅ COMPLETADA | `test_fase12_garantias.py` |
| FASE 14 | Notificaciones por rol | ✅ COMPLETADA | `test_notificaciones.py` |
| FASE 15 | Panel de Configuración centralizado | ✅ COMPLETADA | `test_fase15_configuracion.py` |
| — | Bloques anteriores (mapa, IA, archivos, permisos, AJAX, etc.) | ✅ COMPLETADAS | `test_fase*.py` |
| — | Panel de Configuración | ✅ COMPLETADA | `test_fase15_configuracion.py` |
| — | Multisucursal (operación por sede) | 🟡 PARCIAL | `test_fase3_sedes.py` |
| — | PWA | 🟡 PARCIAL | — |
| — | Calidad (QA integral y cierre) | ⚠️ REQUIERE REVISIÓN | — |
| — | Fases 2–9, 13, 16–22 del plan maestro | 🔴 PENDIENTE | — |

---

## Fases completadas

### FASE 1 — Decimal/migraciones — ✅ COMPLETADA · P0

**Objetivo:** garantizar precisión monetaria (evitar errores de flotantes) y un esquema de
base de datos estable y migrado.

**Funcionalidades existentes**
- Montos monetarios con `Decimal` y columnas `db.Numeric(10,2)` / `Numeric(4,2)` (IVA) en:
  `models/factura.py` (+ `facturas_detalle`), `pago_factura.py`, `cotizacion.py`,
  `cotizacion_item.py`, `inventario.py` (costo promedio ponderado), `servicio.py`,
  `configuracion_taller.py` (IVA configurable), `orden_trabajo.py` y `orden_trabajo_repuesto.py`.
- Cálculos de IVA y totales con `Decimal.quantize` (cotizaciones, facturas).
- Corrección del import `Decimal` (commit `2abe911`).
- Migraciones de esquema aplicadas (ver `migrations/versions/`).

**Qué falta:** verificación/aplicación de las migraciones contra la base de Neon en producción.

**Prioridad:** P0 — crítico.

---

### FASE 10 — Historial / ficha técnica — ✅ COMPLETADA · P1

**Objetivo:** ficha técnica por vehículo con resumen de actividad, inversión acumulada y
mantenimientos preventivos sugeridos.

**Funcionalidades existentes** (`services/historial_service.py`, `routes/vehiculos.py`,
`templates/vehiculos/historial.html`)
- `HistorialService.get_resumen(vehiculo_id)` → visitas, último kilometraje, último servicio,
  total invertido (facturas no anuladas) y conteo por tipo de registro.
- `HistorialService.get_proximos_mantenimientos(vehiculo_id)` con `INTERVALOS_MANTENIMIENTO`
  (aceite 5.000 km, frenos 15.000, balanceo/alineación 10.000, llantas 40.000, batería 30.000)
  y estados `urgente` / `proximo` / `al_dia` / `sin_datos`.
- Vista con 4 tarjetas de ficha técnica, tarjetas de próximos mantenimientos con badges de
  estado y botón de imprimir (usa el print CSS existente en `static/css/siam.css`).
- Auto-registro del historial desde factura, OT entregada y cita completada.

**Qué falta:** exportación PDF/Excel de la ficha técnica (mejora P3, no bloqueante).

**Prioridad:** P1 — importante.

---

### FASE 11 — Cotizaciones — ✅ COMPLETADA · P1

**Objetivo:** presupuestos con ítems, aprobación del cliente y conversión en orden de trabajo.

**Funcionalidades existentes**
- `models/cotizacion.py` + `models/cotizacion_item.py`: estados
  `pendiente / aprobada / rechazada / convertida / vencida`.
- `services/cotizacion_service.py`: crear cotización, agregar ítem desde servicio o ítem libre,
  eliminar ítem, recálculo de IVA/descuento, cambiar estado, `convertir_a_ot` (genera la OT con
  los ítems de servicio), `marcar_vencidas`, consulta por cliente/vehículo.
- `routes/cotizaciones.py` (`/cotizaciones/`) y vistas en `templates/cotizaciones/`.
- Portal del cliente: ver, aprobar y rechazar cotizaciones (`templates/portal/cotizaciones.html`).
- Notificaciones al cliente al crear/enviar y al aprobar/rechazar.
- Migración `a8c4d2f6e1b9_cotizaciones_garantias.py`.

**Qué falta:** vista imprimible/PDF de la cotización (mejora P3).

**Prioridad:** P1 — importante.

---

### FASE 12 — Garantías — ✅ COMPLETADA · P1

**Objetivo:** registro de garantías, generación automática desde OT/servicio y gestión de
reclamaciones.

**Funcionalidades existentes**
- `models/garantia.py`: estados `activa / caducada / reclamada / anulada`, con código
  secuencial (`GAR-000001`), fechas de inicio/fin y nota de reclamación.
- `services/garantia_service.py`: `crear`, `crear_para_ot`, `crear_desde_servicio` (usa
  `servicio.garantia_meses`), `cambiar_estado`, `actualizar_estados_vencidas`, consulta por
  cliente/vehículo.
- `routes/garantias.py` (`/garantias/`) y vistas en `templates/garantias/`.
- Portal del cliente: consulta de garantías (`templates/portal/garantias.html`).
- Notificaciones: cliente al crear la garantía; personal al reclamarla.
- Migración `a8c4d2f6e1b9_cotizaciones_garantias.py`.

**Qué falta:** aviso/agendamiento programado de vencimiento fuera del refresco de listado (P3).

**Prioridad:** P1 — importante.

---

### FASE 14 — Notificaciones por rol — ✅ COMPLETADA · P1

**Objetivo:** notificaciones in-app dirigidas por rol (cliente y personal), con página propia
de consulta.

**Funcionalidades existentes**
- `models/notificacion.py`: `Notificacion` con 8 tipos (`cita, orden, factura, cotizacion,
  garantia, recordatorio, pago, sistema`) y label legible.
- `services/notification_service.py`: `notify`, `notify_roles`, `notify_cliente`, `notify_staff`,
  `unread_count`, `list_for`, `list_all`, `eliminar`, `mark_read`, `mark_all_read`, `to_dict`.
  Protección **IDOR**: marcar/eliminar solo por el dueño de la notificación.
- `routes/notificaciones.py` (`/notificaciones/`): página con filtros por tipo y pendientes,
  borrado (JSON o redirect), y API AJAX (`/api/no-leidas`, `/api/listar`, `/api/leer`,
  `/api/leer-todas`).
- `templates/notificaciones/index.html` + campanilla con contador y "Ver todas" en el navbar.
- Disparadores por rol:
  - OT creada → cliente; OT creada con mecánico → notifica al mecánico
    (`notify_roles(["mecanico"], ...)`); OT `listo_entrega` / `entregado` → cliente.
  - Factura creada → cliente; pago registrado en factura → cliente (`tipo "pago"`).
  - Cita creada → cliente; cita completada → cliente.
  - Nueva solicitud de cita en el portal → personal; cita cancelada en el portal → personal.
  - Cotización creada → cliente; aprobación/rechazo por el cliente → personal y cliente.
  - Garantía creada → cliente; garantía reclamada → personal.
  - Recordatorio generado/creado → cliente.
- Migración `c1a9d4f2e6b8_notificaciones.py`.

**Qué falta:** canal externo (email/WhatsApp/push) para las notificaciones (P3).

**Prioridad:** P1 — importante.

---

### FASE 15 — Panel de Configuración centralizado — ✅ COMPLETADA · P1

**Objetivo:** panel exclusivo para administradores en `/configuracion/` que centralice la
configuración del taller (empresa, apariencia, citas, notificaciones, archivos, asistente IA,
seguridad y sistema), reutilizando la base existente de `ConfiguracionTaller`.

**Funcionalidades existentes**
- `routes/configuracion.py` (blueprint `/configuracion/`, guard `staff_blueprint_guard`):
  `index` redirige a `empresa`; `seccion/<seccion>` para las 9 secciones
  (`empresa, sedes, apariencia, citas, notificaciones, archivos, ia, seguridad, sistema`);
  POST de lectura aborta 405; `sistema_comprobar` (POST → JSON) y `quitar_logo` (POST).
- **Permisos:** solo `admin` escribe (`_admin_o_403`, AJAX → 403 JSON / form → redirect);
  staff (`recepcion`, `mecanico`) lee; `cliente` redirigido a `/portal/`.
- **AJAX:** guardado con `Accept: application/json` + `X-CSRFToken`; `_es_ajax()` distingue
  peticiones JSON (comprueba `request.mimetype` o cabecera `Accept`) porque `request.is_json`
  es `False` para FormData.
- **Empresa:** contacto completo (nombre, NIT, ciudad, dirección, teléfono, WhatsApp, email,
  sitio web, redes), facturación (régimen, prefijo, resolución DIAN, IVA) y logo con
  `ImageService` (guardar/eliminar).
- **Apariencia:** colores HEX validados (`validar_hex()`, `#RRGGBB`/`#RGB`, normalizados a
  mayúsculas) inyectados como variables CSS en `base.html` vía context processor
  `inject_appearance` (`--siam-primary`, `--siam-primary-strong`, `--siam-primary-soft`,
  `--siam-accent`, `--siam-gradient`; fallbacks `#2563EB`, `#1D4ED8`, `#DBEAFE`, `#0F766E`).
- **Citas:** duración de cita (15–240 min), anticipación mínima (0–720 h) y límite de
  cancelación (0–720 h). La anticipación y el intervalo se **aplican** en `routes/citas.py`
  (crear/editar) y `routes/portal.py` (`solicitar_cita`) vía
  `ConfiguracionService.hora_en_intervalo()`.
- **Notificaciones:** toggles email/SMS/WhatsApp y días de antelación de recordatorios
  (1–90). El parámetro queda centralizado y listo para el scheduler externo (pendiente P3).
- **Archivos:** sección de solo lectura con límites configurables por entorno
  (`FILE_MAX_*`, `MAX_CONTENT_LENGTH`) y almacenamiento efímero documentado (Render).
- **IA:** configuración del asistente existente (activado, nombre, tono
  Profesional/Amigable/Técnico, mensaje de bienvenida — ya usado por
  `routes/assistant.py`/`assistant_service.py` —, preguntas sugeridas en JSON una por línea,
  contacto y mensaje de emergencia). Sin API externa nueva.
- **Seguridad:** tarjetas de sesión (8 h), CSRF, rate limit, roles; tabla de usuarios con
  último acceso (`usuario.last_access_at`, registrado al login). **Nunca** muestra
  `SECRET_KEY`, `DATABASE_URL` ni tokens.
- **Sistema:** versión (2.0.0), entorno, estado de BD, migración actual de `alembic_version`
  y botón "Comprobar sistema" (`sistema_comprobar`) con 🟢/🟡/🔴.
- `services/configuracion_service.py` (aplicación de secciones, validación HEX, `css_vars`,
  `preguntas`, `estado_sistema`, `datos_sistema`, `datos_seguridad`) y formularios en
  `forms/configuracion_forms.py` (Empresa/Apariencia/Citas/Notificaciones/IA).
- Migración `b5d7e9a2c1f6_panel_configuracion_centralizado.py` (nuevas columnas en
  `ConfiguracionTaller`, `last_access_at` en `usuario`).
- Las rutas heredadas `/facturas/configuracion` y `/facturas/configuracion/quitar-logo` se
  conservan intactas; el nuevo panel reutiliza la lógica de logo.
- Auditado en `docs/CONFIGURATION_PANEL_AUDIT.md`.

**Qué falta (mejoras P3, no bloqueantes):** canal externo de notificaciones con scheduler que
consuma `notif_recordatorio_dias`, backup/restore, previsualización de marca en vivo.

**Prioridad:** P1 — importante.

---

## Bloques anteriores implementados — ✅ COMPLETADAS

Bloques construidos en iteraciones previas y verificados por la suite
(`tests/test_fase*.py`, `test_portal.py`, `test_inventario.py`, `test_reportes.py`, etc.):

| Bloque | Funcionalidades existentes | Verificación |
|--------|---------------------------|--------------|
| Separación empresa/cliente | Roles (`admin/recepcion/mecanico/cliente`), `usuarios.cliente_id`, portal separado del panel administrativo, configuración del taller (`ConfiguracionTaller`). | `test_fase6_permisos.py`, `test_portal.py` |
| Dashboard empresarial | KPIs (ingresos, por cobrar, ticket promedio, OT retrasadas, % citas completadas, productividad por mecánico, asistencias activas) + actividad reciente. | `test_dashboard_pro.py`, `test_fase8_empresa.py` |
| Dashboard cliente (portal) | Vehículos, citas, facturas, pagos, órdenes, historial, perfil, documentos. | `test_portal.py` |
| Actividad en tiempo real | `/dashboard/api/actividad` + refresco AJAX sin recargar la página. | `test_fase9_ajax.py` |
| Sistema de citas | Agenda con sede, servicio y validación de horarios. | `test_fase3_sedes.py` |
| Órdenes de trabajo | Checklist, repuestos con inventario, fotos, firmas, entrega (kms/combustible), estado "pruebas". | `test_fase4_ordenes.py`, `test_ot_profesional.py` |
| Mapa / sedes | Modelo `Sede`, mapa público, citas y cotizaciones con sede. | `test_fase1_mapa.py`, `test_fase3_sedes.py` |
| Asistencia de emergencia | Solicitudes con ubicación (lat/lon), panel de gestión del personal (en camino/atendido/cancelado), cancelación del cliente. | `test_fase1_mapa.py`, `test_fase10_gestor_asistencias.py` |
| Chat / asistente IA | Chat con memoria de contexto, intents (mecánica, agendar cita, sedes, precios, búsqueda), acciones clicables, IA 2.0 (diagnóstico y mantenimiento predictivo). | `test_fase3_asistente.py`, `test_fase67_chat_contexto.py`, `test_inteligencia.py` |
| Búsqueda | Intents `buscar_cliente`, `buscar_vehiculo`, `buscar_factura`, `consultar_inventario`, stock bajo. | `test_fase3_asistente.py` |
| AJAX | Refresco del dashboard, campanilla de notificaciones, operaciones JSON con `X-CSRFToken`. | `test_fase9_ajax.py` |
| Sistema de imágenes | `ImageService` (validación extensión/mime/tamaño, orientación EXIF, optimización, miniaturas), logo del taller. | `test_fase5_archivos.py` |
| Fotos y archivos | `StorageService` + `Adjunto`, fotos de historial (antes/durante/después), fotos y firmas de OT, portal de documentos. | `test_fase5_archivos.py` |
| Sistema visual | Landing moderna, login con imagen lateral, dashboard con cards/iconos, modo oscuro, print CSS. | `test_fase2_landing.py` |
| Responsive | Sidebar/navbar y vistas adaptadas a móvil (css/js propios). | suite general |
| Seguridad | Decoradores por rol, guarda por blueprint, CSRF en todos los POST, headers de seguridad (CSP, HSTS), rate limiting, validación de entrada. | `test_fase6_permisos.py`, `test_audit.py` |
| Tests | Suite completa de 345 tests + 1 skip, con fixtures de app/db/client. | — |

---

## Backlog — Fases pendientes

### Panel de Configuración — ✅ COMPLETADA · P1

- **Objetivo:** panel centralizado de configuración del taller por parte del admin.
- **Funcionalidades existentes:** módulo propio `/configuracion/` con 9 secciones
  (empresa, sedes, apariencia, citas, notificaciones, archivos, IA, seguridad, sistema),
  permisos solo-admin de escritura, guardado AJAX con CSRF, apariencia por variables CSS,
  validación de citas aplicada en agenda y portal, estado del sistema, y conservación de las
  rutas heredadas de `/facturas/configuracion`. Ver `docs/CONFIGURATION_PANEL_AUDIT.md`.
- **Qué falta (P3):** scheduler de recordatorios externos, backup/restore, previsualización
  de marca en vivo.
- **Prioridad:** P1.

### Multisucursal — 🟡 PARCIAL · P1

- **Objetivo:** operación multi-taller con datos por sede.
- **Funcionalidades existentes:** modelo `Sede` (dirección, teléfono, horario, lat/lon,
  servicios en JSON), mapa público `/sedes`, citas con sede y validación de horarios
  (`SedeService.sede_ocupada`), cotizaciones con sede, `seed_sedes`.
- **Qué falta:** CRUD de sedes (admin), foto por sede, facturas/reportes por sede y
  operación segmentada por sede.
- **Prioridad:** P1.

### PWA — 🟡 PARCIAL · P2

- **Objetivo:** aplicación instalable con soporte offline.
- **Funcionalidades existentes:** `manifest.json`, iconos 192/512, theme color,
  apple touch icon.
- **Qué falta:** service worker, cache offline, instalación completa.
- **Prioridad:** P2.

### Calidad (QA integral y cierre) — ⚠️ REQUIERE REVISIÓN · P0

- **Objetivo:** auditoría y validación integral pre-producción.
- **Funcionalidades existentes:** suite 345 tests verde, `FINAL_AUDIT.md` (78/100 global),
  checklist de pre-producción, auditoría de BD.
- **Qué falta:** revisar/validar PDF WeasyPrint en Linux (Render), aplicar migraciones y
  verificar en Neon, Redis para rate limiting (`RATELIMIT_STORAGE_URI`), corregir los ítems
  pendientes de FINAL_AUDIT (pool, métodos de pago hardcodeados, SEO/accessibilidad).
- **Prioridad:** P0.

### Fases 2–9, 13, 15–22 del plan maestro — 🔴 PENDIENTE · por definir

- El plan maestro (22 fases) no está versionado en el repositorio; las definiciones de estas
  fases están pendientes de confirmar/detallar.
- El trabajo ya implementado que podría corresponder a parte de esas fases está documentado
  en "Bloques anteriores implementados" y **no se marca como fase completa hasta validar la
  numeración oficial**.
- **Prioridad:** a definir (P1–P3 según definición).

---

## PRÓXIMA FASE RECOMENDADA

**Completar la fase de Calidad/QA integral (P0)** o, en paralelo, **Multisucursal (P1).**

Razones:
1. El Panel de Configuración (FASE 15) quedó **completada**: módulo propio `/configuracion/`,
   permisos solo-admin, apariencia, citas, notificaciones, IA, seguridad y sistema, con la
   suite en 374 tests verde.
2. La fase de **Calidad/QA integral** es requisito para producción: validación de PDF
   (WeasyPrint) en Linux/Render, aplicación de migraciones en Neon y cierre de pendientes de
   `FINAL_AUDIT.md`.
3. **Multisucursal** es la siguiente candidata funcional (P1): CRUD de sedes (admin),
   foto por sede y facturas/reportes por sede, apoyada en la base de `test_fase3_sedes.py`.

---

## Notas transversales
- CSRF habilitado en todo el sistema; los POST de formularios deben incluir token.
  En configuración de pruebas el CSRF del test client está desactivado.
- PDF (WeasyPrint): implementado con fallback; requiere validación en Linux (Render).
- Gunicorn no corre en Windows (limitación histórica); producción usa Render/Linux.
- El panel de configuración guarda solo colores HEX validados; nunca CSS arbitrario.
- Números de fase del plan maestro: FASE 1, 10, 11, 12, 14, 15 ya verificadas; los números 2–9,
  13 y 16–22 están pendientes de confirmación oficial antes de marcarse como completadas.
