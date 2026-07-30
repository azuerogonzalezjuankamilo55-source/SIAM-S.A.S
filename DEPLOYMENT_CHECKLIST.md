# SIAM - Deployment Checklist (Render + Neon)

## 1. Variables de entorno en Render Dashboard

| Variable | Sync | Obligatoria | Valor de ejemplo |
|---|---|---|---|
| `FLASK_ENV` | `true` | Sí | `production` |
| `SECRET_KEY` | `false` | Sí | Generar con: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `false` | Sí | Conexión pooled de Neon: `postgresql://user:pass@ep-xxxx-pooler.region.aws.neon.tech/db?sslmode=require` |
| `APP_URL` | `true` | Sí | `https://siam.onrender.com` |
| `DB_POOL_SIZE` | — | No | `3` (default) |
| `DB_POOL_OVERFLOW` | — | No | `5` (default) |
| `DB_POOL_RECYCLE` | — | No | `300` (default) |

Las variables con `sync: false` deben llenarse **manualmente** en el Dashboard de Render
  → Environment → Secret Files. No se sincronizan desde GitHub.

## 2. Build Command

```
pip install -r requirements.txt
```

## 3. Start Command

```
gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT --workers 4 --timeout 120 --access-logfile - --error-logfile -
```

## 4. Configuración de Neon

Usar la **cadena pooled** de Neon (hostname con `-pooler`). Ejemplo:

```
postgresql://user:pass@ep-xxxx-pooler.sa-east-1.aws.neon.tech/db?sslmode=require
```

- La cadena pooled termina en `-pooler.region.aws.neon.tech`
- La cadena directa (sin pooler) puede saturar el límite de conexiones de Neon Free Tier
- La app usa `pool_size=3` y `max_overflow=5` por worker (configurable vía `DB_POOL_SIZE` y `DB_POOL_OVERFLOW`)

### Configuración adicional en Neon Dashboard

1. Ir a https://console.neon.tech → proyecto → **Settings** → **IP Allow**
2. Agregar `0.0.0.0/0` (permitir conexiones desde cualquier IP de Render)
3. Verificar en **Connection Details** que la cadena pooled esté activa

## 5. Migraciones

Antes del primer deploy, ejecutar localmente:

```bash
flask db upgrade
```

O usando el CLI de SIAM:

```bash
python manage.py migrate
```

Esta app **no ejecuta migraciones automáticamente** al importar `create_app()`. Deben ejecutarse manualmente antes de que la app funcione correctamente.

Crear el admin inicial:

```bash
python manage.py create-admin --nombre Admin --correo admin@siam.com --password <secreto>
```

## 6. Health Check

Una vez desplegado:

```bash
curl https://siam.onrender.com/health
```

Respuesta esperada (200):

```json
{"status": "healthy", "app": "SIAM", "version": "2.0.0"}
```

El health check **no consulta la base de datos**, solo verifica que la aplicación responde.

El health check está configurado en `render.yaml`:

```yaml
healthCheckPath: /health
```

Render lo ejecutará automáticamente para determinar si el servicio está vivo.

## 7. Logs de Render

Para revisar logs en Render:

1. Ir al Dashboard de Render → **si**am → **Events** / **Logs**
2. Verificar que no aparezcan errores de:
   - Variables de entorno faltantes (`SECRET_KEY`, `DATABASE_URL`)
   - Timeout de conexión a Neon (`sqlalchemy.exc.TimeoutError`)
   - Permisos denegados
3. Para logs en tiempo real:

```bash
render logs --service siam --follow
```

## 8. Verificación post-deploy

- [ ] `https://siam.onrender.com/health` devuelve 200
- [ ] La página principal carga sin errores 500
- [ ] El login funciona (usar admin creado con `create-admin`)
- [ ] Los logs no muestran `ValueError: Production requires env vars`
- [ ] Los logs no muestran `TimeoutError` de SQLAlchemy

## 9. Referencias

- `config.py` → `ProductionConfig` (pool, validación)
- `render.yaml` → configuración del servicio
- `Procfile` → start command para Gunicorn
