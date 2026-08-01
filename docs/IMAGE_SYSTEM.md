# SIAM — Sistema de Imágenes (ImageService)

Sistema centralizado para validar, optimizar, crear miniaturas y eliminar de forma
segura todas las imágenes que maneja SIAM (fotos de OT, firmas, logo del taller,
imágenes de servicios, fotos de mecánicos, foto de perfil y galerías de historial).

## Dónde se guardan los archivos

- Todas las imágenes se guardan en `static/uploads/<subcarpeta>/`.
- La ruta pública servida es `/static/uploads/<subcarpeta>/<archivo>`.
- En `services/image_service.py` la raíz se calcula con `_upload_root()`:
  si no se pasa `upload_root` usa `current_app.root_path` (raíz del proyecto),
  por lo que el fallback devuelve `<raíz>/static/uploads/`.

### Subcarpetas usadas

| Subcarpeta | Uso | Origen |
|------------|-----|--------|
| `ot` | Fotos del trabajo de una OT | `OrdenTrabajoService.guardar_foto` |
| `firmas` | Firmas de mecánico y cliente | `OrdenTrabajoService.guardar_firma` |
| `logos` | Logo del taller | `routes/facturas.py::configuracion` |
| `servicios` | Imagen del catálogo de servicios | `routes/servicios.py` |
| `mecanicos` | Foto del mecánico | `routes/mecanicos.py` |
| `perfiles` | Foto de perfil del usuario | `routes/portal.py::perfil` |
| `historial` | Galería antes/durante/después del historial del vehículo | `routes/vehiculos.py` |

## Validaciones

- Extensiones permitidas: `jpg`, `jpeg`, `png`, `webp`.
- MIME real validado con Pillow (`Image.open(...).verify()`), no solo la extensión.
- Tamaño máximo: **5 MB**.
- Archivo vacío → error.

## Optimización

- Se redimensiona a **máx. 1600 px** por el lado mayor (`LANCZOS`).
- Se respeta la orientación EXIF (rotación automática 90/180/270).
- JPEG se convierte a RGB; WebP con paleta a RGBA.
- Calidad JPEG/WebP: 85 (`optimize=True`).

## Miniaturas

- Se genera `<archivo>_thumb.webp` (400 px) junto al original.
- El filtro Jinja `img_thumb` (registrado en `app.py`) devuelve la miniatura
  si existe; si no, la original.
- `ImageService.thumb_url(ruta_publica)` permite obtener la miniatura en Python.

## Borrado seguro

- `ImageService.eliminar(ruta_publica)` borra el archivo y su miniatura.
- Guarda `os.path.normpath` contra path traversal: solo borra archivos dentro
  de `static/uploads/` y solo rutas públicas con prefijo `/static/uploads/`.

## Errores

- `ImageError` (subclase de `ValueError`) para cualquier validación o fallo de
  procesamiento. Los servicios lo convierten en `BusinessRuleException` para que
  las rutas muestren un mensaje al usuario (flash).

## Ejemplo de uso

```python
from services.image_service import ImageService

ruta_publica = ImageService.guardar(file, "servicios")  # -> "/static/uploads/servicios/<uuid>.jpg"
ImageService.eliminar(ruta_publica)
```

## Templates

- `templates/vehiculos/historial.html`: galerías por registro con badges de etapa
  (`antes`/`durante`/`despues`), botón "Añadir fotos" y lightbox.
- `templates/ordenes_trabajo/ver.html`: galería de fotos con `img_thumb` y lightbox.
- `templates/partials/sidebar.html` y `templates/partials/navbar.html`: logo del
  taller y avatar del usuario.
- `templates/servicios/*`, `templates/mecanicos/*`, `templates/portal/perfil.html`:
  vista previa y carga de imagen/foto.

## Migración de esquema

La migración `e6f2b7a3c9d1` agrega:

- `servicios.imagen_path` (String 300, nullable).
- `usuarios.foto_path` (String 300, nullable).
- `mecanicos.foto_path` (String 300, nullable).
- Tabla `historial_foto` (id, historial_vehiculo_id FK, tipo, path, descripcion, created_at).

Aplicada a Neon (head `e6f2b7a3c9d1`).
