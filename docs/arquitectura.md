# Arquitectura de SIAM — Sistema Integral Automotriz

## 1. Filosofía General

SIAM sigue una arquitectura limpia en capas (Clean Architecture) con separación clara
de responsabilidades. Cada capa se comunica con la siguiente de forma unidireccional,
favoreciendo el bajo acoplamiento y la alta cohesión.

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTACIÓN                          │
│  routes/  ·  templates/  ·  static/                      │
│  (HTTP, formularios WTForms, vistas Jinja2)              │
├─────────────────────────────────────────────────────────┤
│                     APLICACIÓN                           │
│  services/  ·  forms/  ·  decorators/                    │
│  (lógica de negocio, validación, autorización)           │
├─────────────────────────────────────────────────────────┤
│                      DOMINIO                             │
│  models/  ·  exceptions/                                 │
│  (entidades SQLAlchemy, excepciones de negocio)          │
├─────────────────────────────────────────────────────────┤
│                 INFRAESTRUCTURA                          │
│  database/  ·  config.py  ·  app.py                      │
│  (DB, Flask app factory, logging, errores globales)      │
├─────────────────────────────────────────────────────────┤
│                 TRANSVERSAL                              │
│  Logging  ·  Manejo de excepciones  ·  CLI (manage.py)  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Capa de Presentación

### 2.1. Routes (Blueprints)

9 blueprints con 38 rutas registradas. Cada blueprint maneja un recurso del dominio:

| Blueprint     | Prefijo         | Rutas clave                         |
|---------------|-----------------|-------------------------------------|
| `auth`        | `/auth`         | login, logout, register             |
| `dashboard`   | `/dashboard`    | index                               |
| `clientes`    | `/clientes`     | listar, crear, editar, eliminar     |
| `vehiculos`   | `/vehiculos`    | listar, crear, editar, eliminar     |
| `servicios`   | `/servicios`    | listar, crear, editar, eliminar     |
| `mecanicos`   | `/mecanicos`    | listar, crear, editar, eliminar     |
| `citas`       | `/citas`        | listar, crear, editar, eliminar,    |
|               |                 | cambiar_estado, obtener_vehiculos   |
| `facturas`    | `/facturas`     | listar, crear, ver, pagar, anular   |
| `inventario`  | `/inventario`   | listar, crear, editar, eliminar     |

**Principios aplicados:**
- Cada ruta recibe un formulario WTForms validado (`form.validate_on_submit()`).
- Type hints en todos los parámetros y retornos (`def listar() -> Any`).
- Docstrings descriptivos en cada vista.
- Logging estructurado con `logging.getLogger("siam.routes.<modulo>")`.

### 2.2. Templates (Jinja2)

24 templates HTML con Bootstrap 5, AOS y GSAP:
- `base.html` — layout principal con sidebar, navbar, flash messages.
- `auth/` — login + register (sin sidebar).
- `*/listar.html` — tablas con acciones por fila.
- `*/form.html` — formularios con `{{ form.hidden_tag() }}` para CSRF.
- `errors/` — 403, 404, 500, error.html (genérico para SIAMException).
- `partials/` — navbar.html, sidebar.html.

---

## 3. Capa de Aplicación

### 3.1. Services

- `DashboardService.get_data()` — consultas agregadas (counts, ingresos, stock bajo).
- `FacturaService.generar(FacturaInput)` — orquestación: valida, calcula IVA, genera
  número de factura, persiste y actualiza estado de la cita.

Ambos servicios son stateless (métodos static) y dependen de `db.session` (inyectado
por Flask-SQLAlchemy).

### 3.2. Forms (WTForms)

9 formularios con validación del lado del servidor:

| Form              | Campos clave                        |
|-------------------|-------------------------------------|
| `LoginForm`       | correo (Email), password            |
| `RegisterForm`    | nombre, correo, password            |
| `ClienteForm`     | nombre, telefono, correo, cedula    |
| `VehiculoForm`    | cliente_id, marca, placa, vin       |
| `ServicioForm`    | nombre, precio_estimado, categoria  |
| `MecanicoForm`    | nombre, especialidad, telefono      |
| `CitaForm`        | cliente_id, fecha, hora, estado     |
| `FacturaForm`     | servicio_ids[], descuento           |
| `InventarioForm`  | nombre, cantidad, precio_venta      |

Todos heredan de `FlaskForm`, lo que provee CSRF automático via `{{ form.hidden_tag() }}`.

### 3.3. Decorators

- `@admin_required` — restringe acceso a usuarios con `rol == "admin"`.
- `@limiter.limit("10/minute")` en login (rate limiting).

---

## 4. Capa de Dominio

### 4.1. Modelos SQLAlchemy

9 modelos con relaciones completas:

```
Usuario ── (autenticación, sin FK)
Cliente ── 1:N ── Vehiculo ── 1:N ── Cita ── 1:1 ── Factura ── 1:N ── FacturaDetalle
Cliente ── 1:N ── Cita
Mecanico ── 1:N ── Cita
Servicio ── 1:N ── FacturaDetalle
```

**Optimizaciones:**
- `__allow_unmapped__ = True` para compatibilidad con anotaciones de tipo sin `Mapped[]`.
- `lazy="select"` en relaciones one-to-many (carga bajo demanda, evita N+1 en consultas simples).
- `lazy="joined"` en relaciones one-to-one (Cita → Factura) para carga inmediata.
- `backref` bidireccional con cascade `all, delete-orphan`.
- `__repr__` en todos los modelos para debugging.
- Type hints en todas las columnas (e.g., `nombre: str`).
- Propiedad `stock_bajo` en `Inventario`.

### 4.2. Excepciones de Negocio

Jerarquía de excepciones personalizadas con `status_code` para HTTP:

```
SIAMException (base, status 500)
├── NotFoundException (404)
├── ValidationException (400)
├── BusinessRuleException (409)
├── AuthenticationException (401)
└── AuthorizationException (403)
```

Manejadas globalmente en `app.py` via `@app.errorhandler(SIAMException)`.

---

## 5. Capa de Infraestructura

### 5.1. Base de Datos

- `SQLAlchemy` 2.0 con `Flask-SQLAlchemy` 3.x.
- Soporte multi-entorno: SQLite (dev/test), PostgreSQL/Neon (production).
- Pool de conexiones con `pool_size=5`, `pool_recycle=300`, `pool_pre_ping=True`.
- Migraciones con Flask-Migrate (Alembic).

### 5.2. Configuración

Tres configuraciones vía `config_by_name`:

| Entorno       | DEBUG | DB                             | CSRF | Rate Limit |
|---------------|-------|--------------------------------|------|------------|
| development   | sí    | `SQLITE` o `DATABASE_URL`      | sí   | sí         |
| testing       | no    | `:memory:` SQLite              | no   | no         |
| production    | no    | `DATABASE_URL` (requerida)     | sí   | sí + Redis opcional |

### 5.3. App Factory

`create_app()` en `app.py` orquesta:
1. Carga de configuración
2. Inicialización de extensiones: db, migrate, login_manager, csrf, limiter
3. Logging estructurado (formato `[timestamp] LEVEL name | mensaje`)
4. Registro de blueprints
5. Error handlers globales (404, 500, 403, SIAMException)

---

## 6. Seguridad

| Mecanismo               | Implementación                            |
|-------------------------|-------------------------------------------|
| CSRF                    | Flask-WTF + `{{ form.hidden_tag() }}`     |
| Contraseñas             | Werkzeug `generate_password_hash` / `check_password_hash` |
| Rate limiting           | Flask-Limiter (10 intentos/minuto en login) |
| Autenticación           | Flask-Login (session-based)               |
| Autorización            | Decorador `@admin_required`               |
| Validación              | WTForms con validadores (Email, Length, DataRequired, NumberRange) |

---

## 7. Logging

Logger jerárquico con prefijo `siam.<modulo>`:

| Logger              | Uso                                  |
|---------------------|--------------------------------------|
| `siam.error`        | Excepciones no manejadas (500)       |
| `siam.routes.auth`  | Intentos de login exitosos/fallidos  |
| `siam.routes.*`     | Creación/actualización/eliminación   |
| `siam.factura_service` | Generación de facturas            |
| `siam.dashboard_service` | Carga del dashboard              |

Formato: `[2026-07-28 17:55:34] INFO siam.factura_service | Generando factura para cita 42`

---

## 8. Pruebas

26 tests con pytest (ejecución en ~5s):

| Archivo             | Tests | Cobertura                     |
|---------------------|-------|-------------------------------|
| `test_models.py`    | 10    | Creación y validación de modelos |
| `test_routes.py`    | 12    | HTTP: login, CRUD, auth, health |
| `test_services.py`  | 4     | FacturaService, DashboardService |

**Fixture:** Sesión SQLite `:memory:` + limpieza automática entre tests via `PRAGMA foreign_keys = OFF` + `DELETE FROM` en orden topológico inverso.

---

## 9. CLI (manage.py)

Comandos de administración via Click:

```bash
python manage.py create-admin --nombre Admin --correo admin@siam.com --password secreto
python manage.py seed
python manage.py migrate
```

---

## 10. Mejoras Post-Refactor

### Aplicadas en este refactor:

- **WTForms** — validación del lado del servidor en todos los formularios
- **CSRF** — protección contra falsificación de solicitudes
- **Rate limiting** — 10 intentos/minuto en login
- **Type hints** — en todos los modelos, rutas, servicios
- **Docstrings** — en todas las funciones públicas
- **Logging estructurado** — logger por módulo con formato timestamp
- **Jerarquía de excepciones** — 5 excepciones de negocio con manejo global
- **Decorador admin_required** — control de acceso por rol
- **Error handler global** — captura SIAMException y renderiza template
- **Testing automatizado** — 26 tests con pytest
- **DRY** — formularios WTForms reutilizables, patrón CRUD consistente
- **SOLID** — responsabilidad única por capa, inyección de dependencias (app factory)
- **Clean Architecture** — separación presentation/application/domain/infrastructure

### Pendientes / Mejora continua:

1. Migrar templates a renderizado WTForms (`form.nombre(class="form-control")`)
2. Agregar Redis como backend de rate limiting en producción
3. Paginación en listados con muchas filas
4. Pruebas de integración con PostgreSQL (testcontainers)
5. CI/CD (GitHub Actions)
6. Monitoreo con Prometheus + Grafana
7. Internacionalización (i18n)
8. Documentación de API via OpenAPI/Swagger
