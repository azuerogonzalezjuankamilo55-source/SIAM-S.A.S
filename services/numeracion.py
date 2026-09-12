"""Numeración secuencial de documentos (facturas, OT, cotizaciones, garantías).

Protección contra números duplicados:
- Lock en proceso (threading): serializa llamadas concurrentes dentro del
  mismo worker/proceso.
- Advisory lock transaccional de PostgreSQL: convierte la secuencia en una
  operación atómica entre procesos (gunicorn con varios workers / instancias).
  El lock se libera automáticamente al hacer commit/rollback de la transacción.
"""
import logging
import threading
import zlib

from sqlalchemy import text

from database.db import db

logger = logging.getLogger("siam.numeracion")

_local_lock = threading.Lock()


def _bloquear_postgres(model) -> None:
    """Toma un advisory xact lock en PostgreSQL antes de leer el último número.

    En SQLite es un no-op (los tests usan SQLite; en producción SIAM usa Neon).
    """
    try:
        engine = db.engine
    except Exception:
        return
    try:
        if engine is None or engine.name != "postgresql":
            return
    except Exception:
        return
    # La tabla determina la llave del lock; rangos predecibles por tabla.
    key = zlib.crc32(model.__tablename__.encode("utf-8")) & 0x7FFFFFFF
    try:
        db.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})
    except Exception as e:
        logger.warning(
            "No se pudo tomar advisory lock para %s: %s", model.__tablename__, e
        )


def siguiente_numero(model, prefijo: str, campo: str = "numero", ancho: int = 6) -> str:
    with _local_lock:
        _bloquear_postgres(model)
        ultimo = model.query.order_by(model.id.desc()).first()
        valor = getattr(ultimo, campo, None) if ultimo else None
        marca = f"{prefijo}-"
        if valor and str(valor).startswith(marca):
            try:
                return f"{marca}{int(str(valor)[len(marca):]) + 1:0{ancho}d}"
            except (ValueError, TypeError):
                pass
        return f"{marca}{1:0{ancho}d}"