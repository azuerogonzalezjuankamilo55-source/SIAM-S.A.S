import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from flask_wtf.csrf import validate_csrf

from models.garantia import Garantia, ESTADOS_GARANTIA, ESTADOS_GARANTIA_LABELS
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.servicio import Servicio
from models.orden_trabajo import OrdenTrabajo
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import GarantiaForm
from services.garantia_service import GarantiaService, GarantiaError
from services.notification_service import NotificationService
from services.vehiculo_service import VehiculoService
from decorators import staff_blueprint_guard, roles_required

logger = logging.getLogger("siam.routes.garantias")
garantias_bp = Blueprint("garantias", __name__, url_prefix="/garantias")
garantias_bp.before_request(staff_blueprint_guard)


def _opciones_form(form: GarantiaForm) -> tuple[list, list, list, list]:
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()
    ordenes = OrdenTrabajo.query.order_by(OrdenTrabajo.created_at.desc()).all()
    form.servicio_id.choices = [(0, "Sin servicio")] + [(s.id, s.nombre) for s in servicios]
    return clientes, vehiculos, servicios, ordenes


def _validar_csrf() -> bool:
    try:
        token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if token:
            validate_csrf(token)
        return True
    except Exception:
        return False


@garantias_bp.route("/")
@login_required
def listar() -> Any:
    GarantiaService.actualizar_estados_vencidas()
    garantias = Garantia.query.order_by(Garantia.created_at.desc()).all()
    return render_template(
        "garantias/listar.html",
        garantias=garantias,
        estados=ESTADOS_GARANTIA,
        labels=ESTADOS_GARANTIA_LABELS,
    )


@garantias_bp.route("/crear", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def crear() -> Any:
    form = GarantiaForm()
    clientes, vehiculos, servicios, ordenes = _opciones_form(form)
    if form.validate_on_submit():
        try:
            garantia = GarantiaService.crear(
                cliente_id=form.cliente_id.data,
                vehiculo_id=form.vehiculo_id.data,
                descripcion=form.descripcion.data,
                meses_validez=form.meses_validez.data or 3,
                servicio_id=form.servicio_id.data or None,
            )
            logger.info("Garantía creada: %s", garantia.codigo)
            NotificationService.notify_cliente(
                garantia.cliente_id,
                "garantia",
                "Nueva garantía registrada",
                f"Tu garantía {garantia.codigo} está vigente hasta el {garantia.fecha_fin.strftime('%d/%m/%Y')}.",
                url_for("portal.garantias"),
            )
            if request.is_json:
                return json_success(message="Creada correctamente.", data={"id": garantia.id})
            flash(f"Garantía {garantia.codigo} registrada", "success")
            return redirect(url_for("garantias.ver", id=garantia.id))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("garantias/form.html", form=form, clientes=clientes, vehiculos=vehiculos, servicios=servicios, ordenes=ordenes)


@garantias_bp.route("/ver/<int:id>")
@login_required
def ver(id: int) -> Any:
    garantia = db.get_or_404(Garantia, id)
    return render_template("garantias/ver.html", garantia=garantia, labels=ESTADOS_GARANTIA_LABELS)


@garantias_bp.route("/cambiar-estado/<int:id>/<estado>", methods=["POST"])
@login_required
@roles_required("admin", "recepcion")
def cambiar_estado(id: int, estado: str) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("garantias.listar"))
    nota = request.form.get("nota") or None
    try:
        garantia = GarantiaService.cambiar_estado(id, estado, nota)
        if estado == "reclamada":
            NotificationService.notify_staff(
                "garantia",
                "Garantía reclamada",
                f"La garantía {garantia.codigo} fue reclamada por el cliente."
                + (f" Motivo: {nota}" if nota else ""),
                url_for("garantias.ver", id=garantia.id),
            )
        if request.is_json:
            return json_success(message="Estado actualizado.")
        flash("Estado actualizado", "success")
        return redirect(url_for("garantias.ver", id=garantia.id))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("garantias.listar"))


@garantias_bp.route("/obtener-vehiculos/<int:cliente_id>")
@login_required
def obtener_vehiculos(cliente_id: int) -> Any:
    return jsonify(VehiculoService.listar_para_select(cliente_id))
