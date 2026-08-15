import logging
from typing import Any
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf

from models.orden_trabajo import OrdenTrabajo, ESTADOS_OT
from models.orden_trabajo_historial import OrdenTrabajoHistorial
from models.orden_trabajo_item import OrdenTrabajoItem
from models.orden_trabajo_foto import OrdenTrabajoFoto
from models.orden_trabajo_repuesto import OrdenTrabajoRepuesto
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.mecanico import Mecanico
from models.inventario import Inventario
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import OrdenTrabajoForm
from services.orden_trabajo_service import OrdenTrabajoService, NIVELES_COMBUSTIBLE
from services.notification_service import NotificationService
from exceptions import BusinessRuleException, NotFoundException
from decorators import staff_blueprint_guard

logger = logging.getLogger("siam.routes.ordenes_trabajo")
ordenes_trabajo_bp = Blueprint("ordenes_trabajo", __name__, url_prefix="/ordenes-trabajo")
ordenes_trabajo_bp.before_request(staff_blueprint_guard)


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
                kms_ingreso=form.kms_ingreso.data or None,
                nivel_combustible_ingreso=form.nivel_combustible_ingreso.data or None,
            )
            db.session.add(orden)
            db.session.flush()
            _registrar_historial(orden, None, "Orden de trabajo creada")
            safe_commit()
            logger.info("OT creada: %s", orden.numero)
            NotificationService.notify_cliente(
                orden.cliente_id,
                "orden",
                "Nueva orden de trabajo",
                f"Tu orden {orden.numero} fue registrada en el taller.",
                url_for("portal.ordenes"),
            )
            if orden.mecanico_id:
                NotificationService.notify_roles(
                    ["mecanico"],
                    "orden",
                    "Orden asignada a taller",
                    f"Nueva orden {orden.numero} asignada. Revisa el checklist.",
                    url_for("ordenes_trabajo.ver", id=orden.id),
                )
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
    orden = db.get_or_404(OrdenTrabajo, id)
    inventario = Inventario.query.filter_by(activo=True).order_by(Inventario.nombre).all()
    return render_template(
        "ordenes_trabajo/ver.html", orden=orden, estados=ESTADOS_OT,
        inventario=inventario, niveles_combustible=NIVELES_COMBUSTIBLE,
    )


@ordenes_trabajo_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int) -> Any:
    orden = db.get_or_404(OrdenTrabajo, id)
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
        orden = db.get_or_404(OrdenTrabajo, id)
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
    orden = db.get_or_404(OrdenTrabajo, id)
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
        if estado_nuevo == "entregado":
            try:
                from services.historial_service import HistorialService
                HistorialService.registrar_desde_orden(orden, current_user.id if current_user.is_authenticated else None)
            except Exception as e:
                logger.warning("No se pudo registrar historial de OT %s: %s", orden.numero, e)
        try:
            if estado_nuevo == "listo_entrega":
                NotificationService.notify_cliente(
                    orden.cliente_id,
                    "orden",
                    "Tu vehículo está listo",
                    f"Tu orden {orden.numero} está lista para entrega. ¡Te esperamos!",
                    url_for("portal.ordenes"),
                )
            elif estado_nuevo == "entregado":
                NotificationService.notify_cliente(
                    orden.cliente_id,
                    "orden",
                    "Vehículo entregado",
                    f"Tu orden {orden.numero} fue entregada. ¡Gracias por confiar en nosotros!",
                    url_for("portal.ordenes"),
                )
        except Exception as e:
            logger.warning("No se pudo notificar al cliente de la OT %s: %s", orden.numero, e)
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


@ordenes_trabajo_bp.route("/items/agregar/<int:id>", methods=["POST"])
@login_required
def agregar_item(id: int) -> Any:
    orden = db.get_or_404(OrdenTrabajo, id)
    descripcion = request.form.get("descripcion", "").strip()
    tiempo = request.form.get("tiempo_minutos") or None
    try:
        OrdenTrabajoService.agregar_item(
            orden.id, descripcion,
            tiempo_minutos=int(tiempo) if tiempo else None,
        )
        if request.is_json:
            return json_success(message="Tarea agregada.")
        flash("Tarea agregada al checklist", "success")
    except (BusinessRuleException, NotFoundException, ValueError) as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.ver", id=orden.id))


@ordenes_trabajo_bp.route("/items/toggle/<int:item_id>", methods=["POST"])
@login_required
def toggle_item(item_id: int) -> Any:
    try:
        item = OrdenTrabajoService.toggle_item(item_id)
        estado = "completada" if item.completado else "pendiente"
        if request.is_json:
            return json_success(message=f"Tarea marcada como {estado}.")
        flash(f"Tarea marcada como {estado}", "success")
        return redirect(url_for("ordenes_trabajo.ver", id=item.orden_trabajo_id))
    except NotFoundException as e:
        if request.is_json:
            return json_error(message=str(e)), 404
        flash(str(e), "danger")
        return redirect(url_for("ordenes_trabajo.listar"))


@ordenes_trabajo_bp.route("/items/eliminar/<int:item_id>", methods=["POST"])
@login_required
def eliminar_item(item_id: int) -> Any:
    try:
        item = db.get_or_404(OrdenTrabajoItem, item_id)
        orden_id = item.orden_trabajo_id
        OrdenTrabajoService.eliminar_item(item_id)
        if request.is_json:
            return json_success(message="Tarea eliminada.")
        flash("Tarea eliminada", "success")
        return redirect(url_for("ordenes_trabajo.ver", id=orden_id))
    except NotFoundException as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e)), 404
        flash(str(e), "danger")
        return redirect(url_for("ordenes_trabajo.listar"))


@ordenes_trabajo_bp.route("/repuestos/agregar/<int:id>", methods=["POST"])
@login_required
def agregar_repuesto(id: int) -> Any:
    orden = db.get_or_404(OrdenTrabajo, id)
    inventario_id = request.form.get("inventario_id")
    cantidad = request.form.get("cantidad", "1")
    precio = request.form.get("precio_unitario", "0")
    nota = request.form.get("nota", "")
    try:
        OrdenTrabajoService.agregar_repuesto(
            orden.id,
            inventario_id=int(inventario_id),
            cantidad=int(cantidad),
            precio_unitario=Decimal(precio or "0"),
            nota=nota,
            usuario_id=current_user.id if current_user.is_authenticated else None,
        )
        if request.is_json:
            return json_success(message="Repuesto agregado.")
        flash("Repuesto agregado a la orden", "success")
    except (BusinessRuleException, NotFoundException, ValueError, TypeError) as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.ver", id=orden.id))


@ordenes_trabajo_bp.route("/repuestos/eliminar/<int:repuesto_id>", methods=["POST"])
@login_required
def eliminar_repuesto(repuesto_id: int) -> Any:
    try:
        repuesto = db.get_or_404(OrdenTrabajoRepuesto, repuesto_id)
        orden_id = repuesto.orden_trabajo_id
        OrdenTrabajoService.eliminar_repuesto(
            repuesto_id,
            usuario_id=current_user.id if current_user.is_authenticated else None,
        )
        if request.is_json:
            return json_success(message="Repuesto eliminado.")
        flash("Repuesto eliminado de la orden", "success")
        return redirect(url_for("ordenes_trabajo.ver", id=orden_id))
    except (BusinessRuleException, NotFoundException) as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("ordenes_trabajo.listar"))


@ordenes_trabajo_bp.route("/fotos/agregar/<int:id>", methods=["POST"])
@login_required
def agregar_foto(id: int) -> Any:
    orden = db.get_or_404(OrdenTrabajo, id)
    archivo = request.files.get("foto")
    descripcion = request.form.get("descripcion", "")
    try:
        OrdenTrabajoService.guardar_foto(
            orden.id, archivo, descripcion or None,
            upload_root=current_app.root_path,
        )
        if request.is_json:
            return json_success(message="Foto agregada.")
        flash("Foto agregada a la orden", "success")
    except (BusinessRuleException, NotFoundException) as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.ver", id=orden.id))


@ordenes_trabajo_bp.route("/fotos/eliminar/<int:foto_id>", methods=["POST"])
@login_required
def eliminar_foto(foto_id: int) -> Any:
    try:
        foto = db.get_or_404(OrdenTrabajoFoto, foto_id)
        orden_id = foto.orden_trabajo_id
        OrdenTrabajoService.eliminar_foto(foto_id, upload_root=current_app.root_path)
        if request.is_json:
            return json_success(message="Foto eliminada.")
        flash("Foto eliminada", "success")
        return redirect(url_for("ordenes_trabajo.ver", id=orden_id))
    except NotFoundException as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e)), 404
        flash(str(e), "danger")
        return redirect(url_for("ordenes_trabajo.listar"))


@ordenes_trabajo_bp.route("/firma/<int:id>", methods=["POST"])
@login_required
def subir_firma(id: int) -> Any:
    orden = db.get_or_404(OrdenTrabajo, id)
    tipo = request.form.get("tipo", "")
    archivo = request.files.get("firma")
    try:
        OrdenTrabajoService.guardar_firma(
            orden.id, tipo, archivo, upload_root=current_app.root_path,
        )
        if request.is_json:
            return json_success(message="Firma guardada.")
        flash("Firma guardada", "success")
    except (BusinessRuleException, NotFoundException) as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.ver", id=orden.id))


@ordenes_trabajo_bp.route("/entregar/<int:id>", methods=["POST"])
@login_required
def entregar(id: int) -> Any:
    orden = db.get_or_404(OrdenTrabajo, id)
    kms = request.form.get("kms_salida") or None
    combustible = request.form.get("nivel_combustible_salida") or None
    try:
        OrdenTrabajoService.entregar(
            orden.id,
            kms_salida=int(kms) if kms else None,
            nivel_combustible_salida=combustible,
            usuario_id=current_user.id if current_user.is_authenticated else None,
        )
        try:
            NotificationService.notify_cliente(
                orden.cliente_id,
                "orden",
                "Vehículo entregado",
                f"Tu orden {orden.numero} fue entregada. ¡Gracias por confiar en nosotros!",
                url_for("portal.ordenes"),
            )
        except Exception as e:
            logger.warning("No se pudo notificar la entrega de la OT %s: %s", orden.numero, e)
        if request.is_json:
            return json_success(message="Orden entregada.")
        flash(f"Orden {orden.numero} entregada", "success")
    except (BusinessRuleException, NotFoundException, ValueError) as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("ordenes_trabajo.ver", id=orden.id))
