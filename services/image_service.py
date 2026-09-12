import io
import logging
import os
import re
import uuid

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger("siam.image_service")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
PILLOW_FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
DEFAULT_MAX_FILE_MB = 5
MAX_DIMENSION = 1600
THUMB_DIMENSION = 400
JPEG_QUALITY = 85

FILENAME_RE = re.compile(r"^[A-Za-z0-9_\-]+\.(webp|png|jpe?g)$")


class ImageError(ValueError):
    pass


class ImageService:
    """Validación, optimización, miniaturas y borrado seguro de imágenes.

    Las imágenes se guardan en ``<root>/static/uploads/<subcarpeta>/`` con
    nombres únicos (UUID) y se sirven como ``/static/uploads/<subcarpeta>/...``.
    """

    @staticmethod
    def _upload_root(upload_root: str | None) -> str:
        if upload_root:
            return upload_root
        from flask import current_app

        return current_app.root_path

    @staticmethod
    def _base_dir(upload_root: str | None) -> str:
        return os.path.join(ImageService._upload_root(upload_root), "static", "uploads")

    # ---------- Validación ----------

    @staticmethod
    def validar_extension(filename: str) -> str:
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ImageError("Formato de imagen no permitido (JPG, PNG, WebP)")
        return ext

    @staticmethod
    def validar_mime(file) -> None:
        data = file.read(1024)
        if hasattr(file, "seek"):
            file.seek(0)
        if not data:
            raise ImageError("El archivo está vacío")
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ImageError("El archivo no es una imagen válida")

    @staticmethod
    def max_image_mb() -> float:
        """Límite configurable: config de Flask → env → default."""
        try:
            from flask import current_app

            val = current_app.config.get("FILE_MAX_IMAGE_MB")
            if val:
                return float(val)
        except RuntimeError:
            pass
        try:
            return float(os.getenv("FILE_MAX_IMAGE_MB", DEFAULT_MAX_FILE_MB))
        except (TypeError, ValueError):
            return DEFAULT_MAX_FILE_MB

    @classmethod
    def validar_tamano(cls, size: int | None) -> None:
        max_mb = cls.max_image_mb()
        limite = max_mb * 1024 * 1024
        if size and size > limite:
            raise ImageError(f"La imagen supera el tamaño máximo de {max_mb:g} MB")

    @staticmethod
    def validar(file, filename: str | None = None, size: int | None = None) -> str:
        nombre = filename or getattr(file, "filename", "") or ""
        ext = ImageService.validar_extension(nombre)
        ImageService.validar_tamano(size if size is not None else getattr(file, "content_length", None))
        ImageService.validar_mime(file)
        return ext

    # ---------- Optimización / miniaturas ----------

    @staticmethod
    def _abrir_orientado(file) -> Image.Image:
        imagen = Image.open(file)
        imagen.load()
        if hasattr(imagen, "_getexif") and imagen.getexif():
            exif = imagen.getexif()
            orientacion = exif.get(0x0112)
            if orientacion == 3:
                imagen = imagen.rotate(180, expand=True)
            elif orientacion == 6:
                imagen = imagen.rotate(270, expand=True)
            elif orientacion == 8:
                imagen = imagen.rotate(90, expand=True)
        return imagen

    @staticmethod
    def _optimizar(imagen: Image.Image, fmt: str) -> Image.Image:
        if max(imagen.size) > MAX_DIMENSION:
            imagen.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        if fmt == "JPEG" and imagen.mode not in ("RGB", "L"):
            imagen = imagen.convert("RGB")
        if fmt == "WEBP" and imagen.mode == "P":
            imagen = imagen.convert("RGBA")
        return imagen

    @staticmethod
    def _guardar_optimizada(file, ruta_abs: str, ext: str) -> None:
        fmt = PILLOW_FORMATS[ext]
        imagen = ImageService._abrir_orientado(file)
        imagen = ImageService._optimizar(imagen, fmt)
        if hasattr(file, "seek"):
            file.seek(0)
        if fmt == "JPEG":
            imagen.save(ruta_abs, fmt, quality=JPEG_QUALITY, optimize=True)
        elif fmt == "WEBP":
            imagen.save(ruta_abs, fmt, quality=JPEG_QUALITY, method=6, optimize=True)
        else:
            imagen.save(ruta_abs, fmt, optimize=True)

    @staticmethod
    def _crear_miniatura(ruta_abs: str) -> str | None:
        try:
            imagen = Image.open(ruta_abs)
            imagen.load()
            imagen.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION), Image.LANCZOS)
            if imagen.mode == "P":
                imagen = imagen.convert("RGBA")
            stem, _ = os.path.splitext(ruta_abs)
            thumb_abs = f"{stem}_thumb.webp"
            imagen.save(thumb_abs, "WEBP", quality=80, method=6)
            return thumb_abs
        except Exception as e:
            logger.warning("No se pudo generar miniatura de %s: %s", ruta_abs, e)
            return None

    # ---------- Guardado / borrado ----------

    @staticmethod
    def guardar(file, subcarpeta: str, upload_root: str | None = None,
                generar_miniatura: bool = True) -> str:
        if not file or not getattr(file, "filename", ""):
            raise ImageError("Selecciona un archivo de imagen")

        ext = ImageService.validar(file)

        base = ImageService._base_dir(upload_root)
        dir_abs = os.path.join(base, subcarpeta)
        os.makedirs(dir_abs, exist_ok=True)

        nombre = f"{uuid.uuid4().hex[:20]}.{ext}"
        ruta_abs = os.path.join(dir_abs, nombre)

        try:
            ImageService._guardar_optimizada(file, ruta_abs, ext)
        except Exception as e:
            logger.error("Error optimizando imagen %s: %s", filename := file.filename, e)
            if os.path.exists(ruta_abs):
                os.remove(ruta_abs)
            raise ImageError("No se pudo procesar la imagen") from e

        if generar_miniatura:
            ImageService._crear_miniatura(ruta_abs)

        ruta_publica = f"/static/uploads/{subcarpeta}/{nombre}"
        logger.info("Imagen guardada: %s", ruta_publica)
        return ruta_publica

    @staticmethod
    def _ruta_abs(ruta_publica: str, upload_root: str | None) -> str | None:
        if not ruta_publica:
            return None
        if not ruta_publica.startswith("/static/uploads/"):
            return None
        rel = ruta_publica[len("/static/uploads/") :]
        base = ImageService._base_dir(upload_root)
        ruta = os.path.join(base, rel)
        if not os.path.normpath(ruta).startswith(os.path.normpath(base)):
            return None
        return ruta

    @staticmethod
    def eliminar(ruta_publica: str | None, upload_root: str | None = None) -> None:
        ruta = ImageService._ruta_abs(ruta_publica or "", upload_root)
        if not ruta or not os.path.isfile(ruta):
            return
        for candidata in (ruta, os.path.splitext(ruta)[0] + "_thumb.webp"):
            try:
                if os.path.isfile(candidata):
                    os.remove(candidata)
            except OSError as e:
                logger.warning("No se pudo eliminar %s: %s", candidata, e)

    @staticmethod
    def thumb_url(ruta_publica: str | None, upload_root: str | None = None) -> str | None:
        """Devuelve la URL de la miniatura si existe; si no, la original."""
        if not ruta_publica:
            return None
        ruta = ImageService._ruta_abs(ruta_publica, upload_root)
        if ruta:
            stem, _ = os.path.splitext(ruta)
            thumb = stem + "_thumb.webp"
            if os.path.isfile(thumb):
                stem_url, _ = os.path.splitext(ruta_publica)
                return stem_url + "_thumb.webp"
        return ruta_publica
