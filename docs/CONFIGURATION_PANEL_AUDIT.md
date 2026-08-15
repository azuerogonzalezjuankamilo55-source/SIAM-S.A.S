# Auditoría — Panel de Configuración Centralizado (FASE 15)

**Estado:** ✅ COMPLETADA · suite: `374 passed, 1 skipped`
**Fecha:** 2026-08-14
**Alcance:** panel `/configuracion/` exclusivo para administradores. Centraliza empresa,
apariencia, citas, notificaciones, archivos, asistente IA, seguridad y sistema.

---

## 1. Resumen ejecutivo

El panel reutiliza la base existente de `ConfiguracionTaller` y la expone en un módulo propio,
dejando intactas las rutas heredadas `/facturas/configuracion` y
`/facturas/configuracion/quitar-logo`. Permisos: solo `admin` escribe; staff
(`recepcion`, `mecanico`) lee; `cliente` es redirigido a `/portal/` por
`staff_blueprint_guard`. El guardado es AJAX (JSON + CSRF) con detección vía `_es_ajax()`.
La apariencia se limita a colores HEX validados inyectados como variables CSS en `base.html`.

---

## 2. Inventario de archivos

| Archivo | Rol |
|---------|-----|
| `routes/configuracion.py` | Blueprint `/configuracion/`: `index`, `seccion/<seccion>`, `sistema_comprobar`, `quitar_logo`; `_es_ajax()`, `_admin_o_403()`. |
| `services/configuracion_service.py` | `validar_hex()`, `ConfiguracionService.SECCIONES`, `aplicar()`, `css_vars()`, `preguntas()`, `serializar_preguntas()`, `hora_en_intervalo()`, `estado_sistema()`, `datos_sistema()`, `datos_seguridad()`. |
| `forms/configuracion_forms.py` | `EmpresaConfigForm`, `AparienciaForm` (`validar_color_hex`), `CitasConfigForm`, `NotificacionesConfigForm`, `IAConfigForm`. |
| `templates/configuracion/index.html` | Layout del panel (nav lateral, alerta solo-lectura, JS "Comprobar sistema"). |
| `templates/configuracion/_empresa.html` | Contacto, facturación, redes y logo. |
| `templates/configuracion/_apariencia.html` | Inputs de color + preview HEX. |
| `templates/configuracion/_citas.html` | Duración, anticipación y límite de cancelación. |
| `templates/configuracion/_notificaciones.html` | Toggles email/SMS/WhatsApp y días de recordatorio. |
| `templates/configuracion/_ia.html` | Asistente: activado, nombre, tono, bienvenida, preguntas, contacto, emergencia. |
| `templates/configuracion/_archivos.html` | Tarjetas de límites (MB) y formatos, solo lectura. |
| `templates/configuracion/_sedes.html` | Resumen + enlace a `sedes.index`. |
| `templates/configuracion/_seguridad.html` | Tarjetas de seguridad + tabla de usuarios con último acceso. |
| `templates/configuracion/_sistema.html` | Versión, entorno, BD, migración y botón "Comprobar sistema". |
| `models/configuracion_taller.py` | Columnas nuevas de empresa/apariencia/citas/notificaciones/IA. |
| `models/usuario.py` | `last_access_at`. |
| `migrations/versions/b5d7e9a2c1f6_panel_configuracion_centralizado.py` | Migración (down_revision `a8c4d2f6e1b9`). |
| `app.py` | Registro del blueprint + context processor `inject_appearance`. |
| `templates/base.html` | Bloque `:root { ... }` con `css_vars`. |
| `templates/partials/sidebar.html` | Enlace "Configuración del Sistema" → panel. |
| `routes/auth.py` | Registro de `last_access_at` al login. |
| `routes/citas.py`, `routes/portal.py` | Aplicación de anticipación e intervalo de citas. |
| `routes/assistant.py`, `services/assistant_service.py` | Bienvenida del asistente desde configuración. |
| `tests/test_fase15_configuracion.py` | 29 tests del panel. |
| `docs/SIAM_2.0_ROADMAP.md` | FASE 15 documentada. |

---

## 3. Rutas del panel

| Método | Ruta | Función | Permiso |
|--------|------|---------|---------|
| GET | `/configuracion/` | `index` → redirige a `empresa` | staff |
| GET/POST | `/configuracion/<seccion>` | `seccion` (9 secciones) | GET: staff · POST: admin |
| POST | `/configuracion/sistema/comprobar` | `sistema_comprobar` → JSON de chequeos | staff |
| POST | `/configuracion/quitar-logo` | `quitar_logo` | admin |

- POST sobre secciones de solo lectura (`sedes`, `archivos`, `seguridad`, `sistema`) → **405**.
- Sección desconocida → **404**.
- Staff en POST: AJAX → **403 JSON**; formulario → redirect con flash.
- `cliente`/no autenticado → redirigido por `staff_blueprint_guard`.

---

## 4. Decisiones de diseño

1. **Detección AJAX con `_es_ajax()`** — `request.is_json` es `False` para `FormData`; se
   comprueba `request.mimetype == "application/json"` o cabecera `Accept` con `application/json`.
2. **Apariencia restringida a HEX** — solo `#RRGGBB` / `#RGB`, normalizados a mayúsculas en
   `validar_hex()`; nunca CSS arbitrario. Fallbacks: `#2563EB`, `#1D4ED8`, `#DBEAFE`, `#0F766E`.
3. **Variables CSS en `base.html`** — el context processor `inject_appearance` expone
   `--siam-primary`, `--siam-primary-strong`, `--siam-primary-soft`, `--siam-accent` y
   `--siam-gradient` (y si no hay configuración, usa los fallbacks).
4. **Rutas heredadas conservadas** — `/facturas/configuracion` y `quitar-logo` siguen
   funcionando; el panel nuevo reutiliza la lógica de logo de `ImageService`.
5. **Preguntas sugeridas en JSON** — `ia_preguntas_sugeridas` se almacena como JSON de lista;
   en GET el formulario las muestra una por línea (`preguntas()`).
6. **Solo se configura lo que existe** — la sección IA activa parámetros del asistente actual;
   no agrega integración externa nueva.
7. **Migración encadenada** — la nueva revisión `b5d7e9a2c1f6` usa `down_revision =
   a8c4d2f6e1b9` (head al momento); el matraz acepta la cadena resultante.

---

## 5. Seguridad

- **Nunca se exponen** `SECRET_KEY`, `DATABASE_URL`, tokens ni contraseñas en `seguridad`/`sistema`.
- `datos_seguridad()` reporta sesión (8 h), CSRF, rate limit y roles — sin secretos.
- `datos_sistema()` no incluye URI ni credenciales; solo versión, entorno, estado BD y
  `alembic_version`.
- `quitar_logo` valida CSRF de cabecera/form antes de eliminar.
- Validación de entrada en formularios WTForms (`Length`, `NumberRange`, `validar_color_hex`).
- Guard por blueprint (`staff_blueprint_guard`) para todo el prefijo `/configuracion/`.

---

## 6. Integración

- `last_access_at` registrado en `routes/auth.py` al login.
- Anticipación mínima y límite de cancelación aplicados en `routes/citas.py` y `routes/portal.py`.
- **Intervalo de citas aplicado** en agenda y portal vía `ConfiguracionService.hora_en_intervalo()`
  (la hora debe alinearse a la grilla configurada; defecto 30 min).
- Bienvenida del asistente configurable consumida por `assistant_service._handle_saludo`.
- `notif_recordatorio_dias` queda centralizado en configuración; su consumo por un scheduler de
  recordatorios externo es **pendiente P3** (no existe infraestructura de tareas en el proyecto).

---

## 7. Verificación

- Suite completa: **374 passed, 1 skipped** (345 previos + 29 nuevos del panel).
- Pruebas nuevas cubren: permisos (cliente/staff/admin/anon), AJAX 403/400/405, validación HEX,
  persistencia de empresa/apariencia/citas/notificaciones/IA, no-exposición de secretos,
  `sistema_comprobar`, `quitar_logo`, intervalo de citas aplicado, enlace del sidebar y
  conservación de `/facturas/configuracion`.

---

## 8. Pendientes (mejoras P3, no bloqueantes)

1. Scheduler externo de recordatorios que consuma `notif_recordatorio_dias` y los canales
   `notif_email/sms/whatsapp`.
2. Backup/restore de configuración.
3. Previsualización de marca (colores) en vivo antes de guardar.
4. Exportar el estado del sistema (chequeos) a un log/reporte.
