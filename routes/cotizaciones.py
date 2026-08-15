import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf

from models.cotizacion import Cotizacion, ESTADOS_COTIZACION, ESTADOS_COTIZACION_LABELS
from models.cotizacion_item import CotizacionItem
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.servicio import Servicio
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import CotizacionForm
from services.cotizacion_service import CotizacionService, CotizacionError
from services.sede_service import SedeService
from services.vehiculo_service import VehiculoService
from services.notification_service import NotificationService
from decorators import staff_blueprint_guard

logger = logging.getLogger("siam.routes.cotizaciones")
cotizaciones_bp = Blueprint("cotizaciones", __name__, url_prefix="/cotizaciones")
cotizaciones_bp.before_request(staff_blueprint_guard)


def _opciones_form(form: CotizacionForm) -> tuple[list, list, list]:
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    sedes = SedeService.listar()
    form.sede_id.choices = [(0, "Sin sede")] + [(s["id"], s["nombre"]) for s in sedes]
    return clientes, vehiculos, sedes


def _validar_csrf() -> bool:
    try:
        token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if token:
            validate_csrf(token)
        return True
    except Exception:
        return False


@cotizaciones_bp.route("/")
@login_required
def listar() -> Any:
    cotizaciones = Cotizacion.query.order_by(Cotizacion.created_at.desc()).all()
    return render_template(
        "cotizaciones/listar.html",
        cotizaciones=cotizaciones,
        estados=ESTADOS_COTIZACION,
        labels=ESTADOS_COTIZACION_LABELS,
    )


@cotizaciones_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = CotizacionForm()
    clientes, vehiculos, sedes = _opciones_form(form)
    if form.validate_on_submit():
        try:
            cotizacion = CotizacionService.crear(
                cliente_id=form.cliente_id.data,
                vehiculo_id=form.vehiculo_id.data,
                sede_id=form.sede_id.data or None,
                descripcion=form.descripcion.data,
                validez_dias=form.validez_dias.data or 15,
            )
            logger.info("Cotización creada: %s", cotizacion.numero)
            if request.is_json:
                return json_success(message="Creada correctamente.", data={"id": cotizacion.id})
            flash(f"Cotización {cotizacion.numero} creada. Agrega los ítems del presupuesto.", "success")
            return redirect(url_for("cotizaciones.ver", id=cotizacion.id))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("cotizaciones/form.html", form=form, clientes=clientes, vehiculos=vehiculos, sedes=sedes)


@cotizaciones_bp.route("/ver/<int:id>")
@login_required
def ver(id: int) -> Any:
    cotizacion = db.get_or_404(Cotizacion, id)
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()
    return render_template(
        "cotizaciones/ver.html",
        cotizacion=cotizacion,
        servicios=servicios,
        labels=ESTADOS_COTIZACION_LABELS,
    )


@cotizaciones_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    cotizacion = db.get_or_404(Cotizacion, id)
    if cotizacion.estado not in ("pendiente", "aprobada"):
        flash("Solo se pueden editar cotizaciones pendientes o aprobadas.", "warning")
        return redirect(url_for("cotizaciones.ver", id=cotizacion.id))
    form = CotizacionForm(obj=cotizacion)
    clientes, vehiculos, sedes = _opciones_form(form)
    if form.validate_on_submit():
        try:
            cotizacion.cliente_id = form.cliente_id.data
            cotizacion.vehiculo_id = form.vehiculo_id.data
            cotizacion.sede_id = form.sede_id.data or None
            cotizacion.descripcion = form.descripcion.data
            cotizacion.validez_dias = form.validez_dias.data or 15
            safe_commit()
            if request.is_json:
                return json_success(message="Actualizada correctamente.")
            flash("Cotización actualizada", "success")
            return redirect(url_for("cotizaciones.ver", id=cotizacion.id))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("cotizaciones/form.html", form=form, cotizacion=cotizacion, clientes=clientes, vehiculos=vehiculos, sedes=sedes)


@cotizaciones_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id: int) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.listar"))
    try:
        cotizacion = db.get_or_404(Cotizacion, id)
        db.session.delete(cotizacion)
        safe_commit("No se pudo eliminar.")
        logger.info("Cotización #%s eliminada", id)
        if request.is_json:
            return json_success(message="Eliminada correctamente.")
        flash("Cotización eliminada", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.listar"))


@cotizaciones_bp.route("/items/agregar/<int:id>", methods=["POST"])
@login_required
def agregar_item(id: int) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.ver", id=id))
    servicio_id = request.form.get("servicio_id", type=int)
    cantidad = request.form.get("cantidad", default=1, type=int)
    if not servicio_id:
        flash("Selecciona un servicio.", "warning")
        return redirect(url_for("cotizaciones.ver", id=id))
    try:
        CotizacionService.agregar_item(id, servicio_id, cantidad)
        if request.is_json:
            return json_success(message="Ítem agregado.")
        flash("Ítem agregado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.ver", id=id))


@cotizaciones_bp.route("/items/agregar-libre/<int:id>", methods=["POST"])
@login_required
def agregar_item_libre(id: int) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.ver", id=id))
    descripcion = (request.form.get("descripcion") or "").strip()
    cantidad = request.form.get("cantidad", default=1, type=int)
    try:
        precio = Decimal(str(request.form.get("precio_unitario") or "0"))
    except InvalidOperation:
        precio = Decimal("0")
    if not descripcion or precio <= 0:
        flash("La descripción y el precio son obligatorios.", "warning")
        return redirect(url_for("cotizaciones.ver", id=id))
    try:
        CotizacionService.agregar_item_libre(id, descripcion, cantidad, precio)
        if request.is_json:
            return json_success(message="Ítem agregado.")
        flash("Ítem agregado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.ver", id=id))


@cotizaciones_bp.route("/items/eliminar/<int:item_id>", methods=["POST"])
@login_required
def eliminar_item(item_id: int) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.listar"))
    item = db.get_or_404(CotizacionItem, item_id)
    cotizacion_id = item.cotizacion_id
    try:
        CotizacionService.eliminar_item(cotizacion_id, item_id)
        if request.is_json:
            return json_success(message="Ítem eliminado.")
        flash("Ítem eliminado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.ver", id=cotizacion_id))


@cotizaciones_bp.route("/cambiar-estado/<int:id>/<estado>", methods=["POST"])
@login_required
def cambiar_estado(id: int, estado: str) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.listar"))
    try:
        cotizacion = CotizacionService.cambiar_estado(id, estado)
        if request.is_json:
            return json_success(message="Estado actualizado.")
        flash("Estado actualizado", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.ver", id=id))


@cotizaciones_bp.route("/enviar/<int:id>", methods=["POST"])
@login_required
def enviar(id: int) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.listar"))
    try:
        cotizacion = db.get_or_404(Cotizacion, id)
        if not cotizacion.items:
            raise CotizacionError("Agrega al menos un ítem antes de enviar.")
        NotificationService.notify_cliente(
            cotizacion.cliente_id,
            "cotizacion",
            "Cotización para aprobación",
            f"Tienes una cotización {cotizacion.numero} por $ {cotizacion.total:.2f} para aprobar o rechazar.",
            url_for("portal.cotizacion_detalle", cotizacion_id=cotizacion.id),
        )
        if request.is_json:
            return json_success(message="Cotización enviada al cliente.")
        flash("Cotización enviada al cliente para su aprobación.", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.ver", id=id))


@cotizaciones_bp.route("/convertir-ot/<int:id>", methods=["POST"])
@login_required
def convertir_ot(id: int) -> Any:
    if not _validar_csrf():
        if request.is_json:
            return json_error("CSRF inválido", 403)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("cotizaciones.listar"))
    try:
        ot = CotizacionService.convertir_a_ot(id, mecanico_id=None)
        logger.info("Cotización #%s convertida en OT %s", id, ot.numero)
        NotificationService.notify_cliente(
            ot.cliente_id,
            "orden",
            "Orden generada desde cotización",
            f"Tu orden {ot.numero} fue creada a partir de la cotización aprobada.",
            url_for("portal.ordenes"),
        )
        if request.is_json:
            return json_success(message="Convertida correctamente.", data={"ot_id": ot.id})
        flash(f"Se generó la orden de trabajo {ot.numero}", "success")
        return redirect(url_for("ordenes_trabajo.ver", id=ot.id))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("cotizaciones.ver", id=id))


@cotizaciones_bp.route("/obtener-vehiculos/<int:cliente_id>")
@login_required
def obtener_vehiculos(cliente_id: int) -> Any:
    return jsonify(VehiculoService.listar_para_select(cliente_id))
