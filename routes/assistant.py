import logging
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user

from services.assistant_service import AssistantService
from database.commit import safe_commit, json_success, json_error

logger = logging.getLogger("siam.routes.assistant")
assistant_bp = Blueprint("assistant", __name__, url_prefix="/asistente")


@assistant_bp.route("/")
@login_required
def index():
    if "chat_history" not in session:
        session["chat_history"] = [
            {
                "rol": "asistente",
                "texto": "\u00bfEn qu\u00e9 podemos ayudarte?\n\nPuedes preguntarme sobre mec\u00e1nica, mantenimiento, motos, carros, servicios o asistencia.",
                "hora": datetime.now().strftime("%H:%M"),
            }
        ]
        session.modified = True
    return render_template("asistente/index.html", historial=session["chat_history"])


@assistant_bp.route("/ask", methods=["POST"])
@login_required
def ask():
    mensaje = request.json.get("mensaje", "").strip()
    if not mensaje:
        return jsonify({"error": "Mensaje vacío"}), 400

    logger.info("Consulta al asistente: %s", mensaje)

    try:
        if "chat_history" not in session:
            session["chat_history"] = []

        hora = datetime.now().strftime("%H:%M")
        session["chat_history"].append({"rol": "usuario", "texto": mensaje, "hora": hora})

        respuesta = AssistantService.process_message(mensaje, usuario=current_user)
        session["chat_history"].append({"rol": "asistente", "texto": respuesta["text"], "hora": datetime.now().strftime("%H:%M")})

        if len(session["chat_history"]) > 50:
            session["chat_history"] = session["chat_history"][-50:]

        session.modified = True
    except Exception as e:
        logger.error("Error en asistente: %s", e)
        return jsonify({"error": "Error procesando la consulta"}), 500

    return jsonify({
        "respuesta": respuesta["text"],
        "tipo": respuesta.get("tipo", "texto"),
        "items": respuesta.get("items"),
    })


@assistant_bp.route("/clear", methods=["POST"])
@login_required
def clear():
    try:
        session.pop("chat_history", None)
        session.modified = True
    except Exception as e:
        logger.error("Error al limpiar sesión del asistente: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})
