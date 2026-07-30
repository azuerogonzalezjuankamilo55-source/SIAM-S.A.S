import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from models.orden_trabajo import OrdenTrabajo, ESTADOS_OT
from models.orden_trabajo_historial import OrdenTrabajoHistorial
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.mecanico import Mecanico
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import OrdenTrabajoForm

logger = logging.getLogger("siam.routes.ordenes_trabajo")
ordenes_trabajo_bp = Blueprint("ordenes_trabajo", __name__, url_prefix="/ordenes-trabajo")


def _generar_numero() -> str:
    ultimo = (
        OrdenTrabajo.query
        .order_by(OrdenTrabajo.id.desc())
        .first()
    )
    if ultimo and ultimo.numero and ultimo.numero.startswith("OT-"):
        try:
            last_num = int(ultimo.numero[3:])
            return f"OT-{last_num + 1:06d}"
        except (ValueError, IndexError):
            pass
    return "OT-000001"


def _registrar_historial(orden: OrdenTrabajo, estado_anterior: str | None, observacion: str = "") -> None:
    historial = OrdenTrabajoHistorial(
        orden_trabajo_id=orden.id,
        estado_anterior=estado_anterior,
        estado_nuevo=orden.estado,
        observacion=observacion or None,
        usuario_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(historial)


@ordenes_trabajo_bp.route("/")
@login_required
def listar() -> Any:
    ordenes = OrdenTrabajo.query.order_by(OrdenTrabajo.created_at.desc()).all()
    return render_template("ordenes_trabajo/listar.html", ordenes=ordenes, estados=ESTADOS_OT)


@ordenes_trabajo_bp.route("/crear", methods=["GET", "POST"])
@login_required
def crear() -> Any:
    form = OrdenTrabajoForm()
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    mecanicos = Mecanico.query.filter_by(activo=True).order_by(Mecanico.nombre).all()
    if form.validate_on_submit():
        try:
            orden = OrdenTrabajo(
                numero=_generar_numero(),
                cliente_id=form.cliente_id.data,
                vehiculo_id=form.vehiculo_id.data,
                mecanico_id=form.mecanico_id.data or None,
                fecha_ingreso=form.fecha_ingreso.data,
                fecha_estimada_entrega=form.fecha_estimada_entrega.data,
                diagnostico_inicial=form.diagnostico_inicial.data,
                observaciones=form.observaciones.data,
            )
            db.session.add(orden)
            db.session.flush()
            _registrar_historial(orden, None, "Orden de trabajo creada")
            safe_commit()
            logger.info("OT creada: %s", orden.numero)
            if request.is_json:
                return json_success(message="Creada correctamente.")
            flash(f"Orden {orden.numero} creada exitosamente", "success")
            return redirect(url_for("ordenes_trabajo.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template(
        "ordenes_trabajo/form.html", form=form, orden=None,
        clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos,
    )


@ordenes_trabajo_bp.route("/ver/<int:id>")
@login_required
def ver(id: int) -> Any:
    orden = OrdenTrabajo.query.get_or_404(id)
    return render_template("ordenes_trabajo/ver.html", orden=orden, estados=ESTADOS_OT)


@ordenes_trabajo_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    orden = OrdenTrabajo.query.get_or_404(id)
    form = OrdenTrabajoForm(obj=orden)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    mecanicos = Mecanico.query.filter_by(activo=True).order_by(Mecanico.nombre).all()
    if form.validate_on_submit():
        try:
            form.populate_obj(orden)
            safe_commit()
            logger.info("OT actualizada: %s", orden.numero)
            if request.is_json:
                return json_success(message="Actualizada correctamente.")
            flash(f"Orden {orden.numero} actualizada", "success")
            return redirect(url_for("ordenes_trabajo.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template(
        "ordenes_trabajo/form.html", form=form, orden=orden,
        clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos,
    )


@ordenes_trabajo_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return json_error(message="CSRF inválido"), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("ordenes_trabajo.listar"))
    try:
        orden = OrdenTrabajo.query.get_or_404(id)
        db.session.delete(orden)
        safe_commit("No se pudo eliminar.")
        logger.info("OT eliminada: %s", orden.numero)
        if request.is_json:
            return json_success(message="Eliminada correctamente.")
        flash(f"Orden {orden.numero} eliminada", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.listar"))


@ordenes_trabajo_bp.route("/cambiar-estado/<int:id>", methods=["POST"])
@login_required
def cambiar_estado(id: int) -> Any:
    orden = OrdenTrabajo.query.get_or_404(id)
    estado_nuevo = request.form.get("estado", "")
    observacion = request.form.get("observacion", "")

    if estado_nuevo not in ESTADOS_OT:
        if request.is_json:
            return json_error(message="Estado inválido")
        flash("Estado inválido", "danger")
        return redirect(url_for("ordenes_trabajo.ver", id=id))

    try:
        estado_anterior = orden.estado
        orden.estado = estado_nuevo
        _registrar_historial(orden, estado_anterior, observacion)
        safe_commit()
        logger.info("OT %s: %s -> %s", orden.numero, estado_anterior, estado_nuevo)
        if request.is_json:
            return json_success(message=f"Estado cambiado a: {orden.estado_display}")
        flash(f"Orden {orden.numero} cambiada a: {orden.estado_display}", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.ver", id=id))


@ordenes_trabajo_bp.route("/obtener-vehiculos/<int:cliente_id>")
@login_required
def obtener_vehiculos(cliente_id: int) -> Any:
    vehiculos = Vehiculo.query.filter_by(cliente_id=cliente_id).all()
    return jsonify([
        {"id": v.id, "texto": f"{v.marca} {v.modelo} - {v.placa}"}
        for v in vehiculos
    ])
