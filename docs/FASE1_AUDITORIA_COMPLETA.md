# SIAM 2.0 — FASE 1: Auditoría completa del repositorio

> Fecha: 2026-08-22 · **Solo diagnóstico. Cero modificaciones de código.**
> Evidencia base: `376 passed, 1 skipped` · `compileall OK` · 151 endpoints / 231 refs `url_for` (todas resuelven).
> Complementa a `docs/SIAM_DUPLICATION_AUDIT.md` (duplicación y hallazgos verificados uno a uno).

---

## P0 · INCIDENTE DE PRODUCCIÓN EN RENDER (causa raíz confirmada)

### Síntoma
`psycopg2.errors.InFailedSqlTransaction` / `sqlalchemy.exc.InternalError` → 500 incluso en `GET /`.

### Cadena causal (el InFailedSqlTransaction NO es la causa raíz)
`InFailedSqlTransaction` significa: *una sentencia anterior falló y la transacción quedó abortada; toda sentencia posterior en esa misma transacción responde con este error hasta que haya rollback*. El PRIMER error es un **desfase esquema↔modelo**: la BD de producción está en una revisión Alembic anterior al HEAD del código.

**Consulta #1 que falla** (se ejecuta en cada request con cookie de sesión, vía `flask-login`):

```sql
SELECT usuarios.id, usuarios.nombre, ..., usuarios.last_access_at
FROM usuarios WHERE usuarios.id = N;
-- ERROR: column usuarios.last_access_at does not exist
```

- Origen: `app.py:516-524` (`load_user`) → `db.session.get(Usuario, id)` selecciona TODAS las columnas del modelo.
- El modelo declara la columna (`models/usuario.py:23`); ninguna migración aplicada en prod la crea.

**Consulta #2 que falla** (context processor de TODAS las páginas, `app.py:447-478`):

```sql
SELECT configuracion_taller.id, ..., configuracion_taller.citas_intervalo_min,
       ..., configuracion_taller.ia_activado, ...
FROM configuracion_taller LIMIT 1;
-- ERROR: column ... does not exist  (hasta 26 columnas ausentes)
```

**Por qué 500 "incluso en GET /"**: cualquier visitante con cookie de sesión (p. ej. el admin probando) dispara `load_user` en `before_request`, ANTES de llegar a la ruta pública → excepción sin capturar → 500. Anónimos pueden ver el landing degradado (el context processor traga el error), pero todo panel/login con sesión activa cae.

**Por qué se registra `InFailedSqlTransaction`**: tras el primer fallo, la misma request ejecuta otra sentencia sobre la transacción abortada (render de plantillas de error, queries de servicios) → PostgreSQL responde `25P02 current transaction is aborted` y ese es el último traceback del log.

### Tablas/columnas faltantes y migraciones responsables

| Migración pendiente | Qué agrega |
|---|---|
| `b5d7e9a2c1f6` | `configuracion_taller`: citas_intervalo_min, citas_min_anticipacion_horas, citas_cancelar_limite_horas, notif_email, notif_sms, notif_whatsapp, notif_recordatorio_dias, ia_activado |
| `c2f8a4d6e1b7` | `configuracion_taller`: ciudad, whatsapp, sitio_web, facebook, instagram, twitter, linkedin, color_primario(+fuerte/soft), color_acento, ia_nombre, ia_tono, ia_mensaje_bienvenida, ia_preguntas_sugeridas, ia_contacto, ia_mensaje_emergencia; **usuarios.last_access_at** |
| `d4e8f1a3c5b7` (HEAD) | usuarios.last_access_at (idempotente) + índices recordatorios/citas |

Cadena lineal verificada: `001→002→003→004→13f078e9a1dc→77ac884306b6→3a1c9d55b0e2→a4f2c8e6d1b3→b7d3f1a2c9e4→e6f2b7a3c9d1→c1a9d4f2e6b8→d3b6e8f2a1c4→f4a7e9c3b5d8→a8c4d2f6e1b9→b5d7e9a2c1f6→c2f8a4d6e1b7→d4e8f1a3c5b7`.

### ¿La BD está atrasada respecto al código? SÍ
- `Procfile`: `web: gunicorn 'app:create_app()'` — **no ejecuta migraciones**.
- `render.yaml:6` declara `preDeployCommand: flask db upgrade`, pero SOLO aplica si el servicio fue creado/sincronizado como Blueprint. Si el servicio se creó a mano en el dashboard de Render, ese comando nunca corrió.
- La migración HEAD documenta en comentarios que este mismo incidente ya ocurrió antes (`d4e8f1a3c5b7:33-38`): se corrigió en código, pero **la corrección nunca se aplicó a producción**.

### Solución: aplicar migraciones (NO rollback, NO borrar migraciones, NO tocar datos)

Comando de verificación (Shell de Render):
```bash
flask db current    # mostrará p.ej. a8c4d2f6e1b9 (o anterior) en vez de d4e8f1a3c5b7
```
Comando correctivo (Shell de Render):
```bash
flask db upgrade    # aplica b5d7e9a2c1f6 → c2f8a4d6e1b7 → d4e8f1a3c5b7, en orden
```
Las tres migraciones son aditivas/idempotentes (ADD COLUMN con server_default, chequeos `_column_exists`): cero riesgo para datos existentes. Tras el upgrade, `/health` debe responder `200 {"database": "connected"}`.

Prevención (FASE 2): asegurar que el servicio Render use el Blueprint (`render.yaml`) o configurar manualmente el **Release Command** = `flask db upgrade` en el dashboard; así ningún deploy vuelve a desplegar código más nuevo que el esquema.

Cambios de código necesarios: **ninguno para reactivar producción**. Mejoras recomendadas posteriores: (a) `routes/auth.py:95` devuelve `json_error(str(e))` → filtra detalles SQL al cliente; (b) valor por defecto de `SECRET_KEY` en `config.py:27` solo debe existir fuera de producción (ya lo valida `ProductionConfig.validate()`).

---

## 1. Errores funcionales confirmados (backend+frontend)

| # | Ubicación | Problema | Severidad |
|---|---|---|---|
| 1 | `templates/sedes.html:106` vs `:279` | `onclick="verSedeEnMapa()"` pero la función vive dentro de una IIFE y no está en `window` → ReferenceError, botón muerto | ALTA |
| 2 | `static/js/siam.js` (solo maneja `data-confirm` en `<a>`, líneas 121-144) | 7 formularios destructivos usan `data-confirm-form` sin handler (`cotizaciones/ver.html:128,160,170`, `cotizaciones/listar.html:61`, `portal/cotizacion_detalle.html:69,73`, `garantias/listar.html:56`) → borrados/anulaciones SIN confirmación | ALTA |
| 3 | `templates/portal/documentos.html:47` | `data-confirm` sobre `<form>`: el handler lee `href` (inexistente) y hace submit con `action="null"` → eliminar documento del portal NO llega al endpoint | ALTA |
| 4 | `routes/auth.py:95` | `json_error(str(e))` expone texto del error SQLAlchemy al cliente (regla #24 violada) | ALTA (seguridad) |
| 5 | `templates/partials/sidebar.html:107,204` | Enlaces Recordatorios/Reportes visibles a todo staff; las rutas exigen `@admin_required` → 403 garantizado para recepción/mecánico | MEDIA |
| 6 | `static/uploads/**` público | Firmas/cédulas/documentos servidos sin autenticación por URL directa | MEDIA (seguridad) |
| 7 | Límites de tamaño declarados (`config.py:44-49`, `storage_service.py`) pero no pasados a `ImageService/FileService` desde la mayoría de rutas de subida | MEDIA |
| 8 | `services/assistant_service.py:494,875` | Horario y "sede principal Soacha" hardcodeados (no leen BD/config) | MEDIA |

Falso positivo descartado: `configuracion/_empresa.html:101` botón `disabled` es condicional a modo solo-lectura (correcto).

## 2. Autenticación, roles y sesiones (verificado)
- Roles: `admin/recepcion/mecanico/cliente`; `STAFF_ROLES` único en `decorators/decorators.py:8`.
- Backend enforcement real: `staff_blueprint_guard` en before_request de 15 blueprints staff; portal con `_portal_guard` propio (redirige staff); recordatorios/reportes con `@admin_required`. No se confía solo en ocultar botones. ✔
- Sesiones producción: cookies Secure/HttpOnly/SameSite=Lax, lifetime 8 h (`config.py:60-65`). ✔
- CSRF global activo, **cero exemptions** en el repo. ✔
- Rate limit global 200/h + storage memory (por-worker en gunicorn con 4 workers → límite real ×4; mejoraría con storage compartido). Nota.
- Gap menor: sidebar muestra enlaces admin sin gate (hallazgo #5); `sedes.api` público sin login (`test_audit.py` lo exige — requiere decisión).

## 3. Separación Cliente vs Administración (verificado)
103 rutas staff / 24 cliente / 13 mixtas (datos scoped por usuario) / 10 públicas. Portal scoped por `cliente_id` del usuario autenticado (`PortalService.get_cliente_de_usuario`). Sin pantallas admin accesibles desde cliente. Solapamientos aceptables: 3 pares detalle factura/OT/cotización (staff↔portal) → candidatos a partial compartido.

## 4. Base de datos y consultas
- 28 modelos, relaciones e índices coherentes; migraciones idempotentes listas.
- Consultas lentas/duplicadas: consolidadas en Fase previa (`ReporteService` fuente única; `DashboardService` delega).
- Código muerto sin callers (verificado): `factura_service.py:32,155`, `cotizacion_service.py:191,199`, `garantia_service.py:140`, `sede_service.py:109`.
- Endpoints muertos o solo-test: `citas.eliminar`, `garantias.generar_ot/generar_servicio`, `notificaciones.api_no_leidas`, JS `initAjaxDelete`/`refreshTable` sin uso en plantillas.
- Race condition menor: sin índice único parcial `(sede_id, fecha, hora)` para citas activas.

## 5. Chatbot IA
~30 intents keyword-based + precios/stock reales de BD (no inventa datos). Pendientes de mejora (FASE 5): streaming/indicador "escribiendo", timeout y cancelación de fetch, horario/sede leídos de config, sinónimos para matching difuso, respuestas generales vía modelo externo solo si hay API key (estructura preparada, sin credenciales inventadas). Seguridad IA: sin acceso administrativo ni escrituras peligrosas (intents read-only).

## 6. Citas
Intervalo y anticipación configurables aplicados en crear/editar/portal; validación anti-doble-reserva exacta. **GAP**: no existe grilla de horas disponibles (`horas_disponibles`) — el cliente teclea la hora. Cancelación cliente sujeta a límite configurable.

## 7. Multimedia
Fotos/videos(mp4)/PDF/documentos soportados con validación tipo+MIME+tamaño; adjuntos del portal scoped por propietario. Pendiente: aplicar límites en rutas, proteger `/static/uploads` sensible, `.mov/.avi/.docx` en `detectar_tipo`.

## 8. Pagos (preparación, regla #12)
Modelo `PagoFactura` con estados y métodos (enum `METODOS_PAGO`), sin integración real: correcto según instrucción. Para activar Nequi/Daviplata/PSE harán falta credenciales y un adaptador; hoy NO hay simulación disfrazada de real.

## 9. Frontend / UX / responsive / animaciones
- Dicts estado→color duplicados en 15+ templates; cabeceras repetidas ×38; fetch cliente→vehículo inline ×4.
- CDN sin SRI ni fallback (`base.html:70-75,142-143`); AOS global sin respetar `prefers-reduced-motion` (landing sí lo respeta); breakpoints casi duplicados `siam.css:1129/1136`.
- Botones muertos: los de hallazgos #1-#3 + `data-otro-mensaje` sin handler.
- Consola: errores previstos por #1/#3; sin más referencias rotas detectadas (231 url_for OK).

## 10. SEO
`robots.txt`, `sitemap.xml`, `manifest.json` presentes y ruteados; CSP/HSTS/X-Frame en `after_request`; landing con OG/meta. Panel administrativo no indexable (noindex en base del panel — verificar tag en FASE 6). Nota: `X-XSS-Protection: 0` intencional/moderno.

## 11. Variables de entorno
SECRET_KEY/DATABASE_URL validados en producción (`ProductionConfig.validate`); `.env` cargado solo local; verificar que `.gitignore` incluya `.env` y `siam.log` (chequear en FASE 2). Ninguna clave hardcodeada encontrada.

---

## Plan aprobado para las siguientes fases (sin ejecutar aún)
- **FASE 2 (críticos)**: comando `flask db upgrade` en Render + Release Command permanente; handler `data-confirm-form` + fix `data-confirm` en form (documentos portal); exponer `verSedeEnMapa`; sanitizar `str(e)` en auth; gate admin en sidebar.
- **FASE 3**: partials compartidos detalle factura/OT/cotización; helper CSRF/número secuencial/constantes desde models; eliminar código muerto (con ajuste de tests); límites de subida aplicados; slots de horas disponibles.
- **FASE 4**: ya estructurada (guards verificados); pulir sidebar por rol y menús 403.
- **FASE 5**: chatbot streaming/timeout/cancelación, datos desde config, sinónimos.
- **FASE 6**: macro badge_estado, SRI/fallback CDN, reduced-motion global, responsive dedupe.
- **FASE 7**: suite completa (pytest + compileall + url_map + smoke por rol).
