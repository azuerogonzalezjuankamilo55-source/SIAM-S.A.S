import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from models.vehiculo import Vehiculo
from models.cliente import Cliente
from services.inteligencia_service import InteligenciaService
from database.commit import json_success, json_error
from decorators import staff_blueprint_guard, roles_required

logger = logging.getLogger("siam.routes.inteligencia")
ia_bp = Blueprint("ia", __name__, url_prefix="/ia")
ia_bp.before_request(staff_blueprint_guard)


@ia_bp.route("/")
@login_required
@roles_required("admin", "mecanico")
def index() -> Any:
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    resumen = InteligenciaService.resumen_taller()
    return render_template("ia/index.html", vehiculos=vehiculos, resumen=resumen)


@ia_bp.route("/diagnosticar", methods=["POST"])
@login_required
@roles_required("admin", "mecanico")
def diagnosticar() -> Any:
    vehiculo_id = request.form.get("vehiculo_id") or None
    sintomas = request.form.get("sintomas", "")
    try:
        vehiculo_id = int(vehiculo_id) if vehiculo_id else None
    except (ValueError, TypeError):
        vehiculo_id = None

    resultado = InteligenciaService.diagnosticar(vehiculo_id, sintomas)

    if request.is_json:
        return json_success(data=resultado)

    if not resultado["sintomas"]:
        flash(resultado["consejo"], "warning")
        return redirect(url_for("ia.index"))

    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    resumen = InteligenciaService.resumen_taller()
    return render_template(
        "ia/index.html", vehiculos=vehiculos, resumen=resumen,
        resultado=resultado, sintomas=sintomas, vehiculo_id=vehiculo_id,
    )


@ia_bp.route("/mantenimiento/<int:vehiculo_id>")
@login_required
@roles_required("admin", "mecanico")
def mantenimiento(vehiculo_id: int) -> Any:
    datos = InteligenciaService.recomendar_mantenimiento(vehiculo_id)
    if not datos["vehiculo"]:
        flash("Vehículo no encontrado", "danger")
        return redirect(url_for("ia.index"))
    return render_template("ia/mantenimiento.html", datos=datos)
