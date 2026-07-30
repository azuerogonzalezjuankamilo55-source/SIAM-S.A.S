import logging
from typing import Any

from flask import jsonify
from database.db import db

logger = logging.getLogger("siam.db")


def safe_commit(fail_msg: str = "No se pudo guardar. Intenta nuevamente.") -> None:
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Error en commit DB: %s", str(e), exc_info=True)
        raise RuntimeError(fail_msg) from e


def json_success(data: dict | None = None, message: str = "Guardado correctamente.") -> Any:
    resp = {"success": True, "message": message}
    if data:
        resp.update(data)
    return jsonify(resp)


def json_error(message: str = "No se pudo guardar. Intenta nuevamente.", status: int = 500) -> Any:
    return jsonify({"success": False, "error": message}), status



