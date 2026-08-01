# SIAM 2.0 — Roadmap de Implementación

Documento vivo del plan de migración de SIAM hacia un software profesional para talleres
automotrices. Se actualiza al finalizar cada fase.

- **Entorno dev**: Windows (local), `.venv`.
- **Producción**: Render + Neon PostgreSQL (Linux).
- **Regla de oro**: no romper funcionalidad existente; cada fase deja todos los tests en verde.

---

## Estado del proyecto

| Fase | Descripción | Estado | Tests |
|------|-------------|--------|-------|
| 0 | Dependencias de reportes/PDF | ✅ Completa | 37/37 |
| 1 | Portal del Cliente | ✅ Completa | 51/51 |
| 2 | Historial del Vehículo | ✅ Completa | 63/63 |
| 3 | Órdenes de Trabajo Profesionales | ✅ Completa | 81/81 |
| 4 | Dashboard Pro | ✅ Completa | 89/89 |
| 5 | IA 2.0 | ✅ Completa | 102/102 |
| 6 | Recordatorios | ✅ Completa | 120/120 |
| 7 | Inventario 2.0 | ✅ Completa | 147/147 |
| 8 | Reportes | ✅ Completa | 160/160 |
| 9 | Mejora Visual (imágenes, logo, dashboard, login, landing) | ✅ Completa | 161/161 |
| 10 | Panel de Configuración | ⏳ Pendiente | — |
| 11 | Multisucursal (sedes con foto) | ⏳ Pendiente | — |
| 12 | PWA | ⏳ Pendiente | — |
| 13 | Calidad (QA integral) | ⏳ Pendiente | — |

---

## FASE 0 — Dependencias

### Cambios
- `requirements.txt`: se agregaron `openpyxl==3.1.5`, `weasyprint==69.0`, `cffi==1.17.1`.

### Notas
- openpyxl ya estaba instalado en el venv (3.1.5) → reportes Excel listos para renderizar en Linux.
- WeasyPrint instalado (v69.0) pero **roto en Windows** (faltan libs nativas pango/gobject).
  El PDF tiene fallback en runtime: si falla, muestra mensaje flash y redirige. Debe validarse en Render/Linux.

---

## FASE 1 — Portal del Cliente

### Objetivo
Un portal web donde el cliente registra su vehículo, agenda/cancela citas, consulta facturas,
pagos, órdenes y su historial, y gestiona su perfil.

### Modelos modificados
- `models/Usuario.py`:
  - Nuevo `cliente_id` (FK a `clientes.id`, nullable).
  - Relación `cliente` → `Cliente`.
  - Propiedades `es_cliente` / `es_admin` (por rol o vínculo).
  - Rol por defecto ahora `"cliente"`.

### Modelos nuevos
- `models/historial_vehiculo.py` → `HistorialVehiculo` (usado por la Fase 2):
  - `TIPOS_HISTORIAL` / `TIPOS_HISTORIAL_LABELS`.
  - Backrefs únicos (`historial`, `historial_vehicular` ×3) para evitar conflictos de mapeo
    con `OrdenTrabajo.historial`.

### Formularios nuevos
- `forms/portal_forms.py`: `SolicitarCitaForm`, `PerfilForm`, `CambiarPasswordForm`.

### Servicios nuevos
- `services/portal_service.py`:
  - `PortalData` (dataclass) + `PortalService` (dashboard, vehículos, facturas, pagos, órdenes, historial).

### Rutas nuevas
- `routes/portal.py` (Blueprint `portal_bp`):
  - `/portal/` (dashboard), `/vehiculos`, `/vehiculos/<id>`, `/citas`, `/citas/solicitar`,
    `/citas/<id>/cancelar`, `/facturas`, `/facturas/<id>`, `/facturas/<id>/pdf`,
    `/pagos`, `/ordenes`, `/ordenes/<id>`, `/historial`, `/perfil`, `/perfil/password`.

### Rutas modificadas
- `routes/auth.py`: login con redirección según rol (cliente → portal, admin → dashboard);
  el registro crea o vincula un `Cliente` por correo.
- `routes/__init__.py` y `app.py`: registro de `portal_bp`.

### Plantillas
- `templates/partials/sidebar.html`: menú según rol (`es_cliente` → portal, si no → admin).
- Portal: `vinculo_pendiente.html`, `index.html`, `vehiculos.html`, `vehiculo_detalle.html`,
  `citas.html`, `solicitar_cita.html`, `facturas.html`, `factura_detalle.html`, `pagos.html`,
  `ordenes.html`, `orden_detalle.html`, `historial.html`, `perfil.html`.

### Tests
- `tests/test_portal.py`: 14 tests (registro/login por rol, dashboard, vehículos propios/ajenos,
  citas, facturas, perfil, contraseña).

### Migración
- `migrations/versions/77ac884306b6_portal_cliente_historial_vehiculo.py`
  (crea `historial_vehiculo`, agrega `usuarios.cliente_id` + FK). Aplicada a Neon.

---

## FASE 2 — Historial del Vehículo

### Objetivo
Historial técnico por vehículo con **registro automático** desde el flujo de negocio
(citas, facturas, órdenes) y línea de tiempo visible para el admin.

### Servicios nuevos
- `services/historial_service.py` → `HistorialService`:
  - `registrar(...)`: crea entrada validando `tipo` (ver `TIPOS_HISTORIAL`).
  - `_tipo_para_servicio(...)`: mapea por palabras clave (aceite, frenos, alineación,
    balanceo, llantas, batería, revisión, diagnóstico, reparación, mantenimiento).
  - `registrar_desde_factura(factura)`: una entrada por servicio + entrada resumen `factura`.
  - `registrar_desde_orden(orden)`: entrada `reparacion` al entregar la OT.
  - `registrar_desde_cita(cita)`: entrada `cita` al completarla.
  - `get_historial_vehiculo(vehiculo_id)`: orden descendente por `fecha` + `created_at`.
  - `agregar_observacion(...)`: registro manual tipo `observacion`.

### Rutas modificadas (auto-registro)
- `routes/citas.py` → `cambiar_estado`: al pasar a `completado` registra historial de cita.
- `routes/ordenes_trabajo.py` → `cambiar_estado`: al pasar a `entregado` registra la OT.
- `services/factura_service.py` → `FacturaService.generar()`: registra historial de factura
  tras el commit (con `try/except` que no bloquea la factura si falla el historial).

### Rutas nuevas
- `routes/vehiculos.py` → `/vehiculos/historial/<vehiculo_id>` (GET/POST):
  - GET: línea de tiempo del vehículo.
  - POST: alta manual de registro (tipo, descripción, kilometraje).

### Plantillas nuevas
- `templates/vehiculos/historial.html`: línea de tiempo con badges por tipo, foto si existe,
  y formulario de registro manual.
- `templates/vehiculos/listar.html`: botón "Historial" por vehículo.

### Tests
- `tests/test_historial.py`: 12 tests (service, tipos inválidos, orden de timeline,
  auto-registro por factura/cita/OT, rutas, alta manual, 404).

---

## FASE 3 — Órdenes de Trabajo Profesionales

### Objetivo
Convertir la OT en un documento profesional: checklist de tareas con tiempos, repuestos
asociados con control de inventario, fotos del trabajo, firmas de mecánico/cliente y
registro de entrega (kms y combustible de salida).

### Modelos nuevos
- `models/orden_trabajo_item.py` → `OrdenTrabajoItem` (checklist): descripción, `completado`,
  `tiempo_minutos`, `posicion`.
- `models/orden_trabajo_foto.py` → `OrdenTrabajoFoto`: `path`, `descripcion`.
- `models/orden_trabajo_repuesto.py` → `OrdenTrabajoRepuesto`: `inventario_id`, `cantidad`,
  `precio_unitario`, `nota`, propiedad `subtotal`.

### Modelo modificado
- `models/orden_trabajo.py` (OrdenTrabajo):
  - Columnas nuevas: `kms_ingreso`, `nivel_combustible_ingreso`, `kms_salida`,
    `nivel_combustible_salida`, `fecha_entrega`, `firma_mecanico_path`, `firma_cliente_path`.
  - Relaciones `items`, `fotos`, `repuestos` (cascade delete-orphan, sin backrefs para
    evitar conflictos de mapeo).
  - Propiedades: `items_completados`, `tiempo_total_minutos`, `total_repuestos`.

### Servicios nuevos
- `services/orden_trabajo_service.py` → `OrdenTrabajoService`:
  - Checklist: `agregar_item`, `toggle_item`, `actualizar_item`, `eliminar_item`.
  - Repuestos: `agregar_repuesto` (valida stock, descuenta inventario y registra
    `MovimientoInventario` tipo `salida` con referencia a la OT), `eliminar_repuesto`
    (devuelve stock con movimiento `entrada`).
  - Fotos: `guardar_foto` (valida extensión, guarda en `static/uploads/ot/`),
    `eliminar_foto`.
  - Firmas: `guardar_firma` (mecánico/cliente en `static/uploads/firmas/`).
  - Entrega: `entregar` (fija estado `entregado`, `fecha_entrega`, kms y combustible de
    salida; registra historial del vehículo).

### Formularios modificados
- `forms/orden_trabajo_forms.py`: `OrdenTrabajoForm` con `kms_ingreso` y
  `nivel_combustible_ingreso`.

### Rutas nuevas (Blueprint `ordenes_trabajo`)
- `/items/agregar/<id>`, `/items/toggle/<item_id>`, `/items/eliminar/<item_id>`.
- `/repuestos/agregar/<id>`, `/repuestos/eliminar/<repuesto_id>`.
- `/fotos/agregar/<id>`, `/fotos/eliminar/<foto_id>`.
- `/firma/<id>` (subir firma mecánico/cliente).
- `/entregar/<id>` (finalizar entrega).

### Rutas modificadas
- `ver/<id>`: pasa inventario y niveles de combustible a la plantilla.
- `crear`: persiste `kms_ingreso` y `nivel_combustible_ingreso`.

### Plantillas
- `templates/ordenes_trabajo/ver.html`: tarjeta de checklist (progreso, toggle, tiempos),
  repuestos (tabla + alta/eliminación), fotos (grid + subida/borrado), firmas
  (subida y vista previa) y tarjeta de entrega con datos de salida.

### Tests
- `tests/test_ot_profesional.py`: 18 tests (checklist, stock/repuestos, fotos, firmas,
  entrega con historial de vehículo, rutas).

### Migración
- `migrations/versions/3a1c9d55b0e2_ot_profesional_checklist_fotos_firmas_repuestos.py`
  (tablas `ordenes_trabajo_items/fotos/repuestos` + columnas nuevas en `ordenes_trabajo`).
  Aplicada a Neon (`3a1c9d55b0e2` head).

---

## FASE 4 — Dashboard Pro

### Objetivo
Ampliar el dashboard con indicadores de gestión del taller (cartera, ticket promedio,
cumplimiento, productividad).

### Servicios modificados
- `services/dashboard_service.py` → `DashboardData` y `DashboardService.get_data()`:
  - `por_cobrar`: saldo total de facturas pendientes/parciales.
  - `ticket_promedio`: facturación total / número de facturas (excluye anuladas).
  - `ot_retrasadas_count` / `ot_retrasadas`: OTs con `fecha_estimada_entrega` vencida
    y sin entregar.
  - `tasa_completacion_citas`: % de citas completadas.
  - `ingresos_por_metodo`: total por método de pago.
  - `ot_por_mecanico`: OTs entregadas por mecánico.
  - `ot_en_proceso`: OTs activas ordenadas por antigüedad.

### Rutas modificadas
- `routes/dashboard.py` `/dashboard/api/stats`: expone los nuevos KPIs.

### Plantilla
- `templates/dashboard/index.html`: fila de KPIs Pro (por cobrar, ticket promedio,
  OT retrasadas, % citas completadas), gráficas de ingresos por método de pago y
  productividad por mecánico, tablas de OTs retrasadas y en proceso.

### Tests
- `tests/test_dashboard_pro.py`: 8 tests (métricas vacías, cartera/ticket, retrasadas,
  tasa de completación, métodos de pago, productividad, rutas index/api).

### Nota
- Sin cambios de esquema → sin migración nueva.

---

## FASE 5 — IA 2.0 ✅ Implementada

Asistencia inteligente sobre datos del taller: diagnóstico por síntomas, plan de
mantenimiento predictivo y resumen del taller en lenguaje natural.

### Archivos nuevos
- `services/inteligencia_service.py`: `InteligenciaService` con `BASE_CONOCIMIENTO`
  (10 reglas de síntomas: motor, frenos, vibración, aceite, batería, temperatura,
  dirección, suspensión, humo, llantas). Métodos `diagnosticar(vehiculo_id, sintomas)`,
  `recomendar_mantenimiento(vehiculo_id)` y `resumen_taller()`.
- `routes/inteligencia.py`: blueprint `ia_bp` en `/ia/` (página, POST diagnóstico,
  plan de mantenimiento por vehículo).
- `templates/ia/index.html` y `templates/ia/mantenimiento.html`.

### Lógica
- `diagnosticar`: empareja el texto libre contra las keywords; devuelve causas
  probables, urgencia (baja/media/alta), servicios activos sugeridos del catálogo
  y un consejo (prioridad alta → no circular y cita inmediata).
- `recomendar_mantenimiento`: lee el historial del vehículo y clasifica cada ítem
  (aceite/frenos/balanceo/alineación/rotación/batería) como `al_dia`, `pendiente`,
  `vencido` o `sin_dato` según antigüedad y kilometraje.
- `resumen_taller`: construye un párrafo con los KPIs del `DashboardService`.

### Integración
- Blueprint registrado en `app.py`; enlace "IA 2.0 — Inteligencia" en el sidebar.

### Tests
- `tests/test_inteligencia.py`: 13 tests (diagnóstico por síntoma, urgencias,
  mantenimiento con/sin historial, resumen, rutas con login y POST).

### Suite completa
- 102/102 pruebas pasando.

---

## FASE 6 — Recordatorios ✅ Implementada

Mantenimientos programados y notificaciones a clientes: el sistema detecta
mantenimientos vencidos/por vencer desde el historial y los muestra tanto al admin
como al cliente en su portal.

### Archivos nuevos
- `models/recordatorio.py`: modelo `Recordatorio` (vehiculo, tipo, servicio de
  mantenimiento, título, descripción, fecha programada, estado, canal) más constantes
  `TIPOS_RECORDATORIO`, `ESTADOS_RECORDATORIO`, `TIPOS_MANTENIMIENTO` y labels.
- `services/recordatorio_service.py`: `RecordatorioService` con `generar_mantenimientos()`
  (reusa `InteligenciaService.recomendar_mantenimiento`, no duplica pendientes/enviados),
  `crear_manual()`, `cambiar_estado()`, `get_todos()` y `get_para_cliente()`.
- `routes/recordatorios.py`: blueprint `recordatorios_bp` en `/recordatorios/` (listado
  con filtros, generar automático, crear manual, cambiar estado). Solo admin.
- `templates/recordatorios/index.html` (admin) y `templates/portal/recordatorios.html`
  (cliente, con botón "Agendar cita").

### Integración
- Ruta `/portal/recordatorios` en `routes/portal.py` para el cliente.
- Enlaces en el sidebar (admin y portal).
- Migración `a4f2c8e6d1b3` (tabla `recordatorios` + índices) aplicada en Neon.

### Tests
- `tests/test_recordatorios.py`: 18 tests (generación con/sin historial, sin duplicados,
  manual, estados, filtros, aislamiento por cliente, rutas admin y portal).

### Suite completa
- 120/120 pruebas pasando.

---

## FASE 7 — Inventario 2.0 ✅ Implementada

Control de stock, bajas de producto, kardex global, valorización y alertas de
reposición integradas con el módulo de recordatorios.

### Archivos nuevos
- `services/inventario_service.py`: `InventarioService` con `registrar_movimiento()`
  (valida tipo/cantidad y actualiza costo promedio ponderado), `dar_baja()`,
  `restaurar()`, `valorizacion()` (valor total por cantidad×costo y por categoría),
  `get_kardex()` (filtros por producto/tipo/rango) y `generar_alertas_reposicion()`
  (crea `Recordatorio` tipo `reposicion` sin duplicar).
- `templates/inventario/kardex.html`: libro de movimientos global con filtros.

### Modelo
- `models/inventario.py`: columnas nuevas `motivo_baja`, `fecha_baja`, `usuario_baja_id`;
  propiedades `es_baja`, `stock_bajo`/`stock_critico_alcanzado` que ignoran dados de baja;
  `registrar_movimiento` soporta tipo `baja` (stock → 0).
- `models/movimiento_inventario.py`: tipo `baja` añadido a constantes/labels.
- `models/recordatorio.py`: `vehiculo_id` ahora nullable y tipo `reposicion`
  (alertas de stock sin vehículo asociado).

### Rutas (inventario)
- `listar`: oculta bajas por defecto (filtro "Incluir dados de baja"), cards de valorización.
- Nuevas: `kardex`, `baja/<id>` (motivo obligatorio), `restaurar/<id>`,
  `alertas/generar-recordatorios`.
- `movimiento` y `editar` ahora pasan por `InventarioService`.

### Integración
- Alertas de reposición visibles en `/recordatorios/` (admin) y filtro tipo `reposicion`.
- Enlace "Kardex" en el sidebar (submenú Inventario).
- Migración `b7d3f1a2c9e4` (columnas de baja + `recordatorios.vehiculo_id` nullable) aplicada en Neon.

### Tests
- `tests/test_inventario.py`: 27 tests (movimientos entrada/salida/baja, costo promedio
  ponderado, bajas/restauración, valorización, kardex, alertas de reposición con/sin
  duplicado, rutas admin y visibilidad en recordatorios).

### Suite completa
- 147/147 pruebas pasando.

---

## FASE 8 — Reportes ✅ Implementada

Exportación de indicadores del taller a Excel (openpyxl) y PDF (WeasyPrint) con filtro
por rango de fechas.

### Archivos nuevos
- `services/reporte_service.py`: `ReporteService.build_resumen(desde, hasta)` construye
  un `ReporteData` con:
  - KPIs: ingresos (facturas pagado/parcial, excluye anuladas), facturas del período,
    ticket promedio, cartera pendiente, OTs entregadas, valor del inventario.
  - Ingresos por día y por método de pago (con filtro de rango).
  - Facturación por cliente (top 10) y servicios más vendidos (top 10 por cantidad).
  - OTs por estado, productividad por mecánico y movimientos de inventario por tipo.
  - Todo el filtrado/grupo usa `func.date(created_at)` — misma convención que el dashboard.
- `routes/reportes.py`: blueprint `reportes_bp` en `/reportes/` (solo admin):
  - `index` con formulario de rango de fechas (default: últimos 30 días).
  - `excel`: genera libro con 7 hojas (Resumen, Ingresos por día, Métodos de pago,
    Clientes, Servicios, Mecánicos, Inventario) y lo descarga como `.xlsx`.
  - `pdf`: renderiza `reportes/pdf.html` con WeasyPrint; si falla (p. ej. Windows sin
    libs nativas) muestra flash y redirige — patrón idéntico a `facturas/pdf`.
- `templates/reportes/index.html` (vista con cards y tablas) y `templates/reportes/pdf.html`.

### Integración
- Blueprint importado y registrado en `routes/__init__.py` y `app.py`.
- Enlace "Reportes" en el sidebar (staff).

### Tests
- `tests/test_reportes.py`: 14 tests (ingresos excluye anuladas, cartera, métodos de pago,
  clientes, servicios, OTs/mecánicos, movimientos de inventario, filtro por fechas, rutas
  admin/cliente, Excel con 7 hojas, PDF con skip si WeasyPrint no genera en el entorno).

### Suite completa
- 160/160 pruebas pasando (1 skip de PDF en Windows por libs nativas).

---

## FASE 9 — Mejora Visual ✅ Implementada

Sistema de imágenes seguro (validación, optimización, miniaturas), logo dinámico
del taller, imágenes en servicios/perfil/mecánicos, galerías antes/durante/después
del historial, dashboard con iconos, login con imagen lateral y landing moderna.

### Archivos nuevos
- `services/image_service.py`: `ImageService` + `ImageError` (ver `docs/IMAGE_SYSTEM.md`).
- `models/historial_foto.py`: `HistorialFoto` (tipo `antes/durante/despues`, path,
  descripcion) + constantes `TIPOS_FOTO_HISTORIAL` y labels.

### Archivos modificados
- `requirements.txt`: Pillow en sección `# Images`.
- `app.py`: filtro Jinja `img_thumb` y `taller_config` global (`ConfiguracionTaller`).
- `services/orden_trabajo_service.py`: fotos/firmas delegadas a `ImageService`.
- `routes/facturas.py`: logo del taller vía `ImageService` + endpoint `quitar-logo`.
- `routes/servicios.py`, `routes/mecanicos.py`, `routes/portal.py`: subida de
  imagen/foto (subcarpetas `servicios`, `mecanicos`, `perfiles`).
- `routes/vehiculos.py`: agregar/eliminar fotos del historial (subcarpeta `historial`).
- `services/dashboard_service.py`: `DashboardData` con `total_servicios` y `total_facturas`.
- Modelos: `servicios.imagen_path`, `usuarios.foto_path`, `mecanicos.foto_path`,
  relación `HistorialVehiculo.fotos` (cascade delete-orphan).
- Forms: `ServicioForm.imagen`, `MecanicoForm.foto`, `PerfilForm.foto`,
  `TallerConfigForm.logo` (sin SVG).
- Templates: dashboard con 8 mod-cards con iconos, login split con imagen lateral,
  landing con hero/mockup, sidebar/navbar con logo/avatar, galerías con lightbox
  en historial y OT, listados/forms de servicios y mecánicos con imagen/foto.

### Migración
- `migrations/versions/e6f2b7a3c9d1_mejora_visual_imagenes.py` (columnas
  `imagen_path`/`foto_path` + tabla `historial_foto`). Aplicada a Neon
  (`e6f2b7a3c9d1` head).

### Suite completa
- 161/161 pruebas pasando (1 skip de PDF en Windows por libs nativas).

---

## Pendientes (Fases 10-13)

- **FASE 10 — Panel de Configuración**: parámetros del taller por admin.
- **FASE 11 — Multisucursal**: soporte multi-taller (sedes, incluida foto por sede;
  hoy la data de sedes es estática en `routes/sedes.py`).
- **FASE 12 — PWA**: instalable, offline.
- **FASE 13 — Calidad**: auditoría integral y cierre.

---

## Notas transversales
- CSRF habilitado en todo el sistema; los POST de formularios deben incluir token.
  En configuración de pruebas el CSRF del test client está desactivado.
- PDF (WeasyPrint): implementado con fallback; requiere validación en Linux (Render).
- Gunicorn no corre en Windows (limitación histórica); producción usa Render/Linux.
