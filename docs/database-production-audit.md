# Database Production Audit — SIAM

## 1. Base de datos real utilizada por producción

**Producción (Render):** PostgreSQL 16 en Neon Cloud (`neondb`)

**Conexión:**
- Host: `ep-autumn-haze-aca5pfnt-pooler.sa-east-1.aws.neon.tech`
- Puerto: 5432
- SSL: `require`
- Pooler: PgBouncer integrado de Neon (conexión pooled)

**Desarrollo local:** SQLite (`siam_dev.db`)

**Tests:** SQLite en memoria (`sqlite:///:memory:`)

## 2. Configuración de conexión

### `config.py` — `ProductionConfig`

```python
SQLALCHEMY_DATABASE_URI = _normalize_db_uri(os.getenv("DATABASE_URL"))
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 3,          # configurable via DB_POOL_SIZE
    "max_overflow": 5,       # configurable via DB_POOL_OVERFLOW
    "pool_recycle": 300,     # configurable via DB_POOL_RECYCLE
    "pool_pre_ping": True,
}
```

### `config.py` — `_normalize_db_uri()`

```python
def _normalize_db_uri(uri: str | None) -> str | None:
    if not uri:
        return uri
    uri = uri.strip().strip("\"'")
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://"):]
    return uri
```

**Funcionalidad:**
- Elimina espacios y comillas simples/duales alrededor de la URL
- Normaliza `postgres://` → `postgresql://` (SQLAlchemy >= 2.0 exige `postgresql://`)

## 3. Tablas existentes (modelos)

| Modelo | Tabla en PostgreSQL | Columnas | PK | FKs |
|--------|---------------------|----------|----|-----|
| `Usuario` | `usuarios` | id, nombre, correo (unique), password_hash, rol, activo, created_at | id | — |
| `Cliente` | `clientes` | id, nombre, telefono, correo, direccion, cedula (unique), created_at | id | — |
| `Vehiculo` | `vehiculos` | id, cliente_id, marca, modelo, anio, placa (unique), vin (unique), color, created_at | id | clientes.id |
| `Servicio` | `servicios` | id, nombre, descripcion, precio_estimado, duracion_estimada, categoria, activo, created_at | id | — |
| `Mecanico` | `mecanicos` | id, nombre, telefono, correo, especialidad, activo, created_at | id | — |
| `Cita` | `citas` | id, cliente_id, vehiculo_id, mecanico_id, fecha, hora, estado, descripcion, created_at | id | clientes.id, vehiculos.id, mecanicos.id |
| `OrdenTrabajo` | `ordenes_trabajo` | id, numero (unique), cliente_id, vehiculo_id, mecanico_id, fecha_ingreso, fecha_estimada_entrega, diagnostico_inicial, observaciones, estado, created_at, updated_at | id | clientes.id, vehiculos.id, mecanicos.id |
| `OrdenTrabajoHistorial` | `ordenes_trabajo_historial` | id, orden_trabajo_id, estado_anterior, estado_nuevo, observacion, usuario_id, created_at | id | ordenes_trabajo.id, usuarios.id |
| `Factura` | `facturas` | id, cita_id, orden_trabajo_id, numero (unique), subtotal, iva_porcentaje, iva, descuento, total, metodo_pago, estado, notas, created_at, updated_at | id | citas.id, ordenes_trabajo.id |
| `FacturaDetalle` | `facturas_detalle` | id, factura_id, servicio_id, cantidad, precio_unitario, descuento, subtotal | id | facturas.id, servicios.id |
| `PagoFactura` | `pagos_factura` | id, factura_id, monto, metodo_pago, referencia, estado, usuario_id, notas, created_at | id | facturas.id, usuarios.id |
| `Inventario` | `inventario` | id, nombre, descripcion, sku (unique), codigo_barras, ubicacion, cantidad, precio_compra, precio_venta, costo_promedio, proveedor, categoria_id, stock_minimo, stock_critico, activo, created_at, updated_at | id | categorias_inventario.id |
| `CategoriaInventario` | `categorias_inventario` | id, nombre (unique), descripcion, padre_id | id | categorias_inventario.id (self-ref) |
| `MovimientoInventario` | `movimientos_inventario` | id, inventario_id, tipo, cantidad, saldo_anterior, saldo_posterior, motivo, referencia, usuario_id, created_at | id | inventario.id, usuarios.id |
| `ConfiguracionTaller` | `configuracion_taller` | id, nombre_taller, nit, direccion, telefono, email, logo_path, regimen, prefijo_factura, resolucion_dian, iva_porcentaje, created_at, updated_at | id | — |

**Total: 15 tablas. 0 vistas. 0 índices explícitos** (SQLAlchemy crea índices automáticos para PKs y FKs).

## 4. Causa raíz de la pérdida de datos en producción

### Causa 1 (bloqueante): URL de conexión inválida

**Síntoma en logs de Render:**
```
sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from given URL string
```

**Causa encontrada:**
El valor de `DATABASE_URL` copiado desde Neon al Dashboard de Render contenía **comillas dobles** alrededor de la URL (`"postgresql://..."`). SQLAlchemy no tolera comillas en la cadena de conexión.

**Fix aplicado en `config.py` — `_normalize_db_uri()`:**
```python
def _normalize_db_uri(uri):
    if not uri:
        return uri
    uri = uri.strip().strip("\"'")   # ← elimina espacios y comillas
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://"):]
    return uri
```

### Causa 2 (no bloqueante): Pool de conexiones demasiado grande para Neon Free

**Síntoma:** Timeout esporádico en picos de carga.

**Causa:** `pool_size=10` + `max_overflow=20` × 4 workers = 120 conexiones potenciales.

**Fix aplicado:**
```python
# ProductionConfig
"pool_size": 3,
"max_overflow": 5,
# Ahora: 8 conexiones por worker × 4 workers = 32 conexiones.
# La cadena pooled de Neon (PgBouncer) maneja hasta 100.
```

### Causa 3 (potencial): Migraciones no aplicadas

**Síntoma:** `relation "xxx" does not exist` en primera request.

**Causa:** No se ejecuta `flask db upgrade` durante el build de Render.

**Solución:** Ejecutar manualmente en Render Shell:
```bash
flask db upgrade
```
O incluirlo en `startCommand` (no recomendado — ralentiza el arranque).

## 5. Operaciones que pueden fallar en producción

| Ruta | Operación | Riesgo |
|------|-----------|--------|
| `/auth/register` | `db.session.add()` / `db.session.commit()` | Sin try/except — error 500 si falla commit |
| `/clientes/crear` | `db.session.commit()` | Sin try/except — error 500 si falla |
| `/clientes/editar/<id>` | `db.session.commit()` | Sin try/except |
| `/clientes/eliminar/<id>` | `db.session.delete()` + `commit()` | Sin try/except |
| `/vehiculos/*` | Ídem | Sin try/except en commit |
| `/servicios/*` | Ídem | Sin try/except en commit |
| `/mecanicos/*` | Ídem | Sin try/except en commit |
| `/citas/*` | Ídem | Sin try/except |
| `/ordenes-trabajo/*` | `db.session.add/flush/commit` | Con flush intermedio |
| `/facturas/*` | Transacciones complejas | Mejor manejo (vía FacturaService) |
| `/inventario/*` | Movimientos + commit | Mejor manejo |

## 6. Problemas de arquitectura detectados

### 6.1 Sin rollback en errores de BD

Ninguna ruta (excepto facturas) tiene `try/except` con `db.session.rollback()`. Si ocurre cualquier error de integridad (unique constraint, FK violada, deadlock), la transacción queda abortada y todas las operaciones siguientes en esa sesión fallan hasta que se haga rollback.

### 6.2 Sin logging seguro de errores de BD

Los errores de base de datos no se registran con logging. Se pierde información crítica para debugging.

### 6.3 Posible uso de SQLite en producción

Si `DATABASE_URL` no está configurada en el Dashboard de Render, el fallback es `sqlite:///siam_dev.db`. Render usa un filesystem efímero — los datos escritos en SQLite se pierden en cada deploy. Esto explicaría "datos que no se guardan".

### 6.4 Validación `ProductionConfig.validate()` no chequea la URL

ANTES del fix: `validate()` solo verificaba que las env vars existieran, no que fueran parseables por SQLAlchemy.

DESPUÉS del fix: ahora también ejecuta `validate_database_url()` que llama a `make_url()` de SQLAlchemy.

### 6.5 Pool config compartido entre Config y ProductionConfig

ANTES: `Config` base tenía `pool_size=10, max_overflow=20`. `ProductionConfig` heredaba esos valores sin override explícito.

DESPUÉS: `Config` base solo tiene `pool_pre_ping: True`. `ProductionConfig` define su propio pool conservador.

## 7. Soluciones aplicadas

| Problema | Archivo | Líneas | Solución |
|----------|---------|--------|----------|
| URL con comillas/espacios | `config.py` | 8-14 | `_normalize_db_uri()` ahora hace `.strip().strip("\"'")` |
| URL no validada | `config.py` | 17-23 | Nueva `validate_database_url()` usa `make_url()` para validar |
| Pool agresivo | `config.py` | 64-69 | `ProductionConfig` con `pool_size=3, max_overflow=5` + env override |
| Sin rollback en rutas | — | — | Pendiente: agregar en Fase 2 |
| Sin logging de errores DB | — | — | Pendiente: agregar en Fase 2 |

## 8. Pendientes

- [ ] Agregar `try/except` con `db.session.rollback()` en TODAS las rutas POST/PUT/DELETE
- [ ] Agregar logging seguro de errores de BD (sin exponer DATABASE_URL ni contraseñas)
- [ ] Verificar que `flask db upgrade` se haya ejecutado en la base de Neon
- [ ] Verificar que las tablas existen realmente en PostgreSQL
- [ ] Verificar que los nombres de columnas tipo `db.func.now()` son compatibles con PostgreSQL
- [ ] Agregar migración inicial si no existe
