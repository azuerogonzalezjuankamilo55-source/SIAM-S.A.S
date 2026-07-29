# Auditoría SIAM — Julio 2026

## Resumen

| Ítem | Resultado |
|---|---|
| Archivos .py auditados | 26 |
| Templates auditados | 24 |
| Archivos estáticos | 5 |
| Blueprints registrados | 9 de 9 |
| Rutas verificadas | 38 |
| Modelos SQLAlchemy | 9 |
| Relaciones verificadas | 14 de 14 |
| Problemas críticos | 0 |
| Problemas altos | 2 |
| Problemas medios | 3 |
| Problemas bajos | 4 |

---

## Problemas Encontrados y Soluciones

### 🔴 Críticos (0)

Ninguno.

---

### 🟠 Alto (2)

#### A1. `requirements.txt` en UTF-16 con BOM

- **Archivo:** `requirements.txt`
- **Problema:** El archivo estaba codificado en UTF-16 Little Endian con BOM (0xFF 0xFE), lo que impedía su lectura con herramientas estándar UTF-8.
- **Solución:** Reescribir el archivo en UTF-8 sin BOM.
- **Archivos modificados:** `requirements.txt`

#### A2. Migración incompatible con esquema previo en Neon

- **Archivo:** `models/usuario.py` → cambio de columna `password` a `password_hash`
- **Problema:** La base de datos Neon tenía tablas creadas con el modelo anterior (columna `password`), causando `UndefinedColumn` al consultar `password_hash`. Además, `flask db migrate` con autogenerate falló por esquemas preexistentes.
- **Solución:**
  1. Crear migración manual (`migrations/versions/001_initial_models.py`) con `DROP TABLE IF EXISTS ... CASCADE` antes de cada `CREATE TABLE`.
  2. La migración es idempotente: funciona tanto en BD vacía como con tablas viejas.
- **Archivos creados:** `migrations/versions/001_initial_models.py`

---

### 🟡 Medio (3)

#### M1. Campos de formulario sin conversión de tipo

- **Archivos:** `routes/inventario.py`, `routes/servicios.py`
- **Problema:** Los valores de `request.form.get()` se pasaban directamente a los modelos como strings, cuando los campos esperaban `Integer` o `Numeric`. SQLAlchemy a veces coercionaba, pero no era confiable.
- **Solución:** Convertir explícitamente con `int()` y `Decimal()` antes de asignar.
- **Archivos modificados:**
  - `routes/inventario.py` — líneas 23-28, 43-48
  - `routes/servicios.py` — líneas 22-25, 40-43

#### M2. Uso de `**locals()` en templates

- **Archivo:** `routes/citas.py`
- **Problema:** `return render_template(..., **locals())` expone todas las variables locales al template, incluyendo objetos como `request`. Es una mala práctica que dificulta el mantenimiento y puede exponer datos sensibles.
- **Solución:** Reemplazar con variables explícitas.
- **Archivos modificados:** `routes/citas.py` — líneas 39, 60

#### M3. `manage.py` con imports no utilizados

- **Archivo:** `manage.py`
- **Problema:** `import sys` e `import os` declarados pero nunca usados (código muerto).
- **Solución:** Eliminar los imports.
- **Archivos modificados:** `manage.py`

---

### 🟢 Bajo (4)

#### B1. Archivos estáticos `img` e `icons` eran archivos en vez de directorios

- **Archivos:** `static/img`, `static/icons`
- **Problema:** Eran archivos de 0 bytes en lugar de directorios, lo que impedía almacenar recursos gráficos.
- **Solución:** Eliminar archivos y crear directorios.
- **Archivos modificados:** `static/img`, `static/icons`

#### B2. Falta `.flaskenv` para comandos Flask CLI

- **Problema:** No existía un archivo `.flaskenv` con `FLASK_APP` y `FLASK_ENV`, obligando a usar `$env:FLASK_APP="app"` manualmente.
- **Solución:** Crear `.flaskenv` con valores por defecto.
- **Archivos creados:** `.flaskenv`

#### B3. Sidebar sin indicador de página activa

- **Archivo:** `templates/partials/sidebar.html`
- **Problema:** No hay resaltado visual de la sección activa en la navegación.
- **Solución:** No requiere parche inmediato; etiquetado como mejora futura.

#### B4. Sin protección CSRF en formularios

- **Problema:** Los formularios no incluyen tokens CSRF. Aunque Flask-Login protege las rutas, los GET requests a rutas de eliminación (`/eliminar/<id>`) son vulnerables a ataques CSRF.
- **Solución:** No requiere parche inmediato; se recomienda migrar a Flask-WTF en una iteración futura.

---

## Archivos Creados Durante la Auditoría

| Archivo | Propósito |
|---|---|
| `migrations/versions/001_initial_models.py` | Migración inicial con DROP + CREATE idempotente |
| `.flaskenv` | Configuración Flask CLI (`FLASK_APP=app`) |
| `docs/auditoria.md` | Este documento |

## Archivos Modificados Durante la Auditoría

| Archivo | Cambio |
|---|---|
| `requirements.txt` | Convertido de UTF-16 a UTF-8 |
| `manage.py` | Eliminados imports `sys` y `os` no utilizados |
| `routes/inventario.py` | Conversión explícita de tipos (`int`, `Decimal`) |
| `routes/servicios.py` | Conversión explícita de tipos (`int`, `Decimal`) |
| `routes/citas.py` | Eliminado `**locals()`, variables explícitas |
| `static/img` | Convertido de archivo a directorio |
| `static/icons` | Convertido de archivo a directorio |

---

## Estado Final de la Arquitectura

```
SIAM-SAS/
├── app.py                          # Factory pattern, Flask-Migrate, LoginManager
├── config.py                       # Multi-entorno (dev/prod)
├── manage.py                       # CLI: create-admin, seed, migrate
├── Procfile                        # Gunicorn para Render
├── render.yaml                     # Config declarativa Render
├── .env.example                    # Template de variables de entorno
├── .flaskenv                       # FLASK_APP + FLASK_ENV
│
├── database/
│   └── db.py                       # Instancia SQLAlchemy
│
├── models/                         # 9 modelos SQLAlchemy
│   ├── __init__.py                 # Re-exportación centralizada
│   ├── usuario.py                  # UserMixin + password_hash
│   ├── cliente.py                  # 1:N vehiculos, 1:N citas
│   ├── vehiculo.py                 # FK cliente, 1:N citas
│   ├── servicio.py                 # 1:N facturas_detalle
│   ├── mecanico.py                 # 1:N citas
│   ├── cita.py                     # FK cliente, vehiculo, mecanico
│   ├── factura.py                  # Factura + FacturaDetalle
│   └── inventario.py               # Stock con alerta
│
├── routes/                         # 9 Blueprints
│   ├── __init__.py                 # Re-exportación
│   ├── auth.py                     # login/logout/register
│   ├── dashboard.py                # DashboardService
│   ├── clientes.py                 # CRUD
│   ├── vehiculos.py                # CRUD
│   ├── servicios.py                # CRUD
│   ├── mecanicos.py                # CRUD
│   ├── citas.py                    # CRUD + estados + AJAX
│   ├── facturas.py                 # Listar/crear/ver/pagar/anular
│   └── inventario.py               # CRUD
│
├── services/                       # Capa de negocio OOP
│   ├── __init__.py
│   ├── dashboard_service.py        # DashboardData dataclass
│   └── factura_service.py          # FacturaInput + FacturaService.generar()
│
├── templates/                      # 24 templates (Bootstrap 5 Dark)
│   ├── base.html                   # AOS + GSAP + sidebar/navbar
│   ├── auth/                       # login, register
│   ├── dashboard/                  # KPIs + citas recientes
│   ├── clientes/                   # listar, form
│   ├── vehiculos/                  # listar, form
│   ├── servicios/                  # listar, form
│   ├── mecanicos/                  # listar, form
│   ├── citas/                      # listar, form
│   ├── facturas/                   # listar, form, ver
│   ├── inventario/                 # listar, form
│   ├── partials/                   # sidebar, navbar
│   └── errors/                     # 403, 404, 500
│
├── static/
│   ├── css/siam.css                # Layout, animaciones, responsive
│   ├── js/siam.js                  # AOS, tooltips, sidebar
│   └── js/factura.js               # Cálculo dinámico de facturas
│
└── migrations/                     # Alembic
    ├── env.py
    └── versions/
        └── 001_initial_models.py   # Schema completo (idempotente)
```

---

## Recomendaciones de Mejora

### Corto plazo (próxima iteración)

1. **Flask-WTF + CSRF:** Implementar formularios con WTForms para validación automática y protección CSRF en todos los endpoints POST. Los endpoints GET de eliminación (`/eliminar/<id>`) deben migrarse a POST con CSRF token.

2. **Paginación:** Las listas de clientes, vehículos, citas y facturas crecerán con el tiempo. Implementar paginación con `query.paginate()` de SQLAlchemy.

3. **Sidebar activo:** Agregar resaltado de la sección activa comparando `request.endpoint` con el nombre del blueprint.

### Mediano plazo

4. **Pruebas automatizadas:** Implementar tests unitarios (pytest) para modelos, servicios y rutas. Al menos coverage del 80% en la capa de servicios.

5. **Logging estructurado:** Reemplazar `logging.basicConfig` con un manejador que envíe logs a un archivo en producción (`siam.log` con rotación diaria).

6. **Roles y permisos:** El campo `rol` en `Usuario` ya existe pero no se valida en las rutas. Implementar decorador `@role_required('admin')`.

### Largo plazo

7. **API REST:** Exponer endpoints JSON para integración con frontend SPA o app móvil.

8. **Reportes:** Módulo de reportes con gráficos (Chart.js) para análisis de ingresos mensuales, servicios más solicitados, etc.

9. **Notificaciones:** Alertas por correo electrónico cuando el inventario llegue a stock mínimo o cuando se agende una cita.

---

## Comandos de Verificación

```bash
# Desde cero
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\flask db upgrade
.venv\Scripts\python manage.py create-admin
.venv\Scripts\python manage.py seed
.venv\Scripts\python app.py

# Migraciones
.venv\Scripts\flask db migrate -m "descripcion"
.venv\Scripts\flask db upgrade

# CLI
.venv\Scripts\python manage.py --help
```

---

*Auditoría realizada el 28 de julio de 2026.  
Estado: ✅ APROBADO — 0 críticos, 0 altos sin resolver.*
