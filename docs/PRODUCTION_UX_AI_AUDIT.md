# SIAM — Auditoría de Overhaul: Producción, UX y Asistente IA

## Resumen

Overhaul completo de SIAM para prepararlo para producción en Render (Neon PostgreSQL), modernizar la UX con AJAX, y expandir el asistente IA con detección de intenciones, emergencia, ubicación y sedes.

## 1. Base de datos y Persistencia

### Problema raíz
- `sqlalchemy.exc.ArgumentError` al parsear `DATABASE_URL` con PgBouncer (Neon) por espacios, quotes o formato inesperado.
- `db.session.commit()` sin manejo de errores causaba sesiones rotas ( `"This session is in 'prepared' state"` ) en producción.

### Soluciones aplicadas
| Archivo | Cambio |
|---|---|
| `config.py` | `_normalize_db_uri()`: strip whitespace/quotes; `validate_database_url()`: verifica parseo; pool conservador en ProductionConfig (`pool_size=3`, `max_overflow=5` con override via `DB_POOL_SIZE`, `DB_POOL_OVERFLOW`) |
| `Procfile`, `render.yaml` | Eliminado `--log-level info` del comando start |
| `database/commit.py` (nuevo) | `safe_commit()` con rollback + log; `json_success()` / `json_error()` helpers |
| 11 rutas (auth, dashboard, clientes, vehiculos, servicios, mecanicos, citas, ordenes_trabajo, facturas, inventario, assistant) | Try/except/rollback en cada `db.session.commit()` + soporte JSON en responses |

### Documentación relacionada
- `DEPLOYMENT_CHECKLIST.md` — pasos para deploy en Render
- `docs/database-production-audit.md` — auditoría detallada de 15 tablas

## 2. UX Moderna con AJAX

### JS (`static/js/siam.js`)
| Módulo | Función |
|---|---|
| AJAX Forms | `initAjaxForms()` — submit con fetch, feedback toast, actualización parcial del DOM |
| AJAX Delete | `initAjaxDelete()` — confirmación modal + delete fetch + animación de salida |
| Dashboard | Auto-refresh cada 30s vía `initDashboardRefresh()` |
| Geolocalización | `initLocationButton()` — obtiene lat/lng del navegador y envía a `/api/ubicacion` |
| Chat Asistente | `initChat()` — typing indicator, timestamps, action buttons, Enter to send, auto-resize textarea, `clearChat()` |

### Sidebar (`templates/partials/sidebar.html`)
- Enlace "Sedes" (`bi-geo-alt`) agregado entre Asistente IA y Clientes

## 3. Asistente IA — Sistema de Intenciones

### `services/assistant_service.py` (reescrito)
- `INTENT_KEYWORDS` dict con palabras clave multi-idioma para clasificación semántica
- 15 intents existentes mantenidos + 6 nuevos:

| Intento | Keywords | Tipo respuesta |
|---|---|---|
| `asistencia_emergencia` | grúa, remolque, accidente, choque, varado | botones (llamar/ubicación) |
| `precios_y_pagos` | precio, costo, tarifa, cuánto cobran, pago, transferencia | botones (planes/detalle) |
| `asistencia_con_ubicacion` | llegar, cómo llegar, dirección, mapa | botones (compartir/mapa) |
| `vehiculos_carga_pesada` | carga pesada, camión, furgón, flota | botones (cotizar/llamar) |
| `ubicaciones` | sede, sucursal, taller, están, dónde | botones (ver mapa/llamar) |
| `repuestos` | repuesto, pieza, filtro, bujía, pastilla de freno | botones (inventario/cotizar) |

## 4. Nuevas Rutas y Modelos

### `routes/sedes.py`
- Datos estáticos de 3 sedes (Norte, Centro, Sur) con dirección, teléfono, horarios, coordenadas
- Ruta `GET /sedes` → `templates/sedes.html` con Leaflet + OpenStreetMap

### `routes/api.py`
| Endpoint | Método | Descripción |
|---|---|---|
| `/api/ubicacion` | POST | Recibe `{latitud, longitud}` del cliente (login required) |
| `/api/asistencia` | GET | Lista las emergencias del usuario actual |
| `/api/asistencia` | POST | Crea una solicitud de asistencia (login required) |

### `models/asistencia.py`
- `AsistenciaEmergencia`: id, usuario_id (FK), latitud, longitud, estado (pendiente/en_curso/resuelta), created_at

### `app.py` y `routes/__init__.py` y `models/__init__.py`
- Registro de `sedes_bp` y `api_bp`; import de `AsistenciaEmergencia`

## 5. Templates

| Template | Cambio |
|---|---|
| `templates/asistente/index.html` | Chat UI moderna: card full-height, typing dots, textarea auto-resize, CSRF oculto, método `clearChat()` |
| `templates/sedes.html` (nuevo) | Leaflet map + branch cards con dirección, teléfono, horarios |

## 6. Tests

- **26/26 tests pasan** (0 fallos)
- Test previamente fallido `test_register_post` corregido: password `"pass123"` → `"pass1234"` (7→8 chars, validación `Length(min=8)`)
- Se agregaron tests de imports para nuevos módulos (`sedes_bp`, `api_bp`, `AsistenciaEmergencia`, `database.commit` helpers)

## 7. Próximos Pasos Recomendados

- [ ] **Deploy a Render**: seguir `DEPLOYMENT_CHECKLIST.md`, configurar variables de entorno en Dashboard
- [ ] **Pruebas de integración**: probar flujo completo con Neon PostgreSQL real
- [ ] **Notificaciones push**: Service Worker + Push API para alertas de emergencia y citas
- [ ] **Reportes**: dashboard con gráficos (Chart.js) de ingresos, órdenes, clientes nuevos
- [ ] **Seguridad**: rate limiting, auditoría de JWT/CSRF, Content Security Policy headers
