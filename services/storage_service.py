import logging
import os
import uuid

from werkzeug.utils import secure_filename

from database.db import db
from models.usuario import Usuario
from models.adjunto import Adjunto

logger = logging.getLogger("siam.storage")

# Extensiones y MIME por tipo de archivo.
TIPOS_ARCHIVO = {
    "imagen": {
        "exts": {"jpg", "jpeg", "png", "webp"},
        "mimes": {"image/jpeg", "image/png", "image/webp"},
        "max_mb_var": "FILE_MAX_IMAGE_MB",
        "max_mb_default": 5,
    },
    "video": {
        "exts": {"mp4"},
        "mimes": {"video/mp4"},
        "max_mb_var": "FILE_MAX_VIDEO_MB",
        "max_mb_default": 100,
    },
    "pdf": {
        "exts": {"pdf"},
        "mimes": {"application/pdf"},
        "max_mb_var": "FILE_MAX_PDF_MB",
        "max_mb_default": 15,
    },
    "documento": {
        "exts": {"pdf", "jpg", "jpeg", "png", "webp"},
        "mimes": {"application/pdf", "image/jpeg", "image/png", "image/webp"},
        "max_mb_var": "FILE_MAX_IMAGE_MB",
        "max_mb_default": 5,
    },
}


class FileError(ValueError):
    pass


def _env_float(var: str, default: float) -> float:
    try:
        return float(os.getenv(var, str(default)))
    except ValueError:
        return default


class FileService:
    """Guarda archivos (imagen, video, PDF) de forma segura.

    Valida extensión, MIME y tamaño (límites configurables por variables de
    entorno). Las imágenes pasan por ``ImageService`` (optimización y
    miniatura); video y PDF se guardan tal cual con nombre UUID.
    """

    @staticmethod
    def _max_bytes(tipo: str) -> int:
        cfg = TIPOS_ARCHIVO.get(tipo, TIPOS_ARCHIVO["documento"])
        mb = _env_float(cfg["max_mb_var"], cfg["max_mb_default"])
        return int(mb * 1024 * 1024)

    @staticmethod
    def max_mb(tipo: str) -> int:
        cfg = TIPOS_ARCHIVO.get(tipo, TIPOS_ARCHIVO["documento"])
        return int(_env_float(cfg["max_mb_var"], cfg["max_mb_default"]))

    @staticmethod
    def detectar_tipo(filename: str, mime: str | None = None) -> str | None:
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
        for tipo, cfg in TIPOS_ARCHIVO.items():
            if ext in cfg["exts"] and (mime is None or mime in cfg["mimes"]):
                return tipo
        return None

    @staticmethod
    def validar(tipo: str, file, filename: str | None = None, size: int | None = None) -> str:
        cfg = TIPOS_ARCHIVO.get(tipo)
        if not cfg:
            raise FileError("Tipo de archivo no soportado.")

        nombre = filename or getattr(file, "filename", "") or ""
        ext = (nombre.rsplit(".", 1)[-1] if "." in nombre else "").lower()
        if ext not in cfg["exts"]:
            raise FileError(f"Extensión no permitida para {tipo}.")

        limite = FileService._max_bytes(tipo)
        tamano = size if size is not None else getattr(file, "content_length", None)
        if tamano is None:
            # Con multipart los navegadores no envían Content-Length por parte
            # (content_length llega None): medir el stream real para que el
            # límite por tipo sea efectivo.
            stream = getattr(file, "stream", file)
            try:
                pos = stream.tell()
                stream.seek(0, os.SEEK_END)
                tamano = stream.tell()
                stream.seek(pos)
            except (OSError, ValueError):
                tamano = None
        if tamano is not None and tamano > limite:
            raise FileError(f"El archivo supera el máximo de {FileService.max_mb(tipo)} MB.")

        data = file.read(1024)
        if hasattr(file, "seek"):
            file.seek(0)
        if not data:
            raise FileError("El archivo está vacío.")

        mime = getattr(file, "mimetype", None)
        if mime and mime not in cfg["mimes"]:
            raise FileError(f"El contenido no coincide con un archivo de tipo {tipo}.")
        return ext

    @staticmethod
    def _base_dir(upload_root: str | None = None) -> str:
        if upload_root:
            return os.path.join(upload_root, "static", "uploads")
        from flask import current_app

        return os.path.join(current_app.root_path, "static", "uploads")

    @staticmethod
    def guardar(tipo: str, file, subcarpeta: str) -> str:
        from services.image_service import ImageService

        if not file or not getattr(file, "filename", ""):
            raise FileError("Selecciona un archivo.")

        ext = FileService.validar(tipo, file)

        base = FileService._base_dir()
        dir_abs = os.path.join(base, subcarpeta)
        os.makedirs(dir_abs, exist_ok=True)
        nombre = f"{uuid.uuid4().hex[:20]}.{ext}"
        ruta_publica = f"/static/uploads/{subcarpeta}/{nombre}"

        if tipo == "imagen":
            ruta_publica = ImageService.guardar(file, subcarpeta)
        else:
            ruta_abs = os.path.join(dir_abs, nombre)
            file.save(ruta_abs)
            logger.info("Archivo guardado: %s", ruta_publica)
        return ruta_publica

    @staticmethod
    def _ruta_abs(ruta_publica: str) -> str | None:
        if not ruta_publica or not ruta_publica.startswith("/static/uploads/"):
            return None
        base = FileService._base_dir()
        rel = ruta_publica[len("/static/uploads/") :]
        ruta = os.path.join(base, rel)
        if not os.path.normpath(ruta).startswith(os.path.normpath(base)):
            return None
        return ruta

    @staticmethod
    def eliminar(ruta_publica: str | None) -> None:
        from services.image_service import ImageService

        if not ruta_publica:
            return
        if ruta_publica.startswith("/static/uploads/"):
            ImageService.eliminar(ruta_publica)
            return
        ruta = FileService._ruta_abs(ruta_publica)
        if ruta and os.path.isfile(ruta):
            try:
                os.remove(ruta)
            except OSError as e:
                logger.warning("No se pudo eliminar %s: %s", ruta, e)


class AdjuntoService:
    """Persistencia y consulta de adjuntos por usuario (propietario)."""

    @staticmethod
    def crear(
        usuario: Usuario,
        tipo: str,
        file,
        entidad_tipo: str | None = None,
        entidad_id: int | None = None,
        subcarpeta: str = "adjuntos",
    ) -> Adjunto:
        nombre_original = secure_filename(getattr(file, "filename", "") or "archivo")
        ruta = FileService.guardar(tipo, file, subcarpeta)
        adj = Adjunto(
            usuario_id=usuario.id,
            tipo=tipo,
            nombre_original=nombre_original,
            path=ruta,
            mime=getattr(file, "mimetype", None),
            tamano=getattr(file, "content_length", None),
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
        )
        db.session.add(adj)
        db.session.commit()
        return adj

    @staticmethod
    def listar(usuario_id: int, entidad_tipo: str | None = None, entidad_id: int | None = None) -> list[Adjunto]:
        q = Adjunto.query.filter_by(usuario_id=usuario_id)
        if entidad_tipo:
            q = q.filter_by(entidad_tipo=entidad_tipo)
        if entidad_id is not None:
            q = q.filter_by(entidad_id=entidad_id)
        return q.order_by(Adjunto.created_at.desc()).all()

    @staticmethod
    def eliminar(usuario_id: int, adjunto_id: int) -> bool:
        adj = Adjunto.query.filter_by(id=adjunto_id, usuario_id=usuario_id).first()
        if not adj:
            return False
        FileService.eliminar(adj.path)
        db.session.delete(adj)
        db.session.commit()
        return True
