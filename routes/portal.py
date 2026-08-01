import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user

from models.cliente import Cliente
from models.cita import Cita
from models.configuracion_taller import ConfiguracionTaller
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import SolicitarCitaForm, PerfilForm, CambiarPasswordForm
from services.portal_service import PortalService
from services.recordatorio_service import RecordatorioService

logger = logging.getLogger("siam.routes.portal")
portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


def _cliente_actual() -> Cliente | None:
    if not current_user.is_authenticated:
        return None
    return PortalService.get_cliente_de_usuario(current_user)


@portal_bp.route("/")
@login_required
def index() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        flash("Tu cuenta no está vinculada a un cliente del taller. Contacta al administrador.", "warning")
        return render_template("portal/vinculo_pendiente.html")
    data = PortalService.get_data(cliente)
    return render_template("portal/index.html", data=data)


@portal_bp.route("/vehiculos")
@login_required
def vehiculos() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = PortalService.get_vehiculos(cliente)
    return render_template("portal/vehiculos.html", cliente=cliente, vehiculos=lista)


@portal_bp.route("/vehiculos/<int:vehiculo_id>")
@login_required
def vehiculo_detalle(vehiculo_id: int) -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    vehiculo = PortalService.get_vehiculo(cliente, vehiculo_id)
    if not vehiculo:
        flash("Vehículo no encontrado", "danger")
        return redirect(url_for("portal.vehiculos"))
    citas = Cita.query.filter_by(vehiculo_id=vehiculo.id).order_by(Cita.fecha.desc(), Cita.hora.desc()).all()
    return render_template("portal/vehiculo_detalle.html", vehiculo=vehiculo, citas=citas)


@portal_bp.route("/citas")
@login_required
def citas() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = (
        Cita.query.filter_by(cliente_id=cliente.id)
        .order_by(Cita.fecha.desc(), Cita.hora.desc())
        .all()
    )
    return render_template("portal/citas.html", cliente=cliente, citas=lista)


@portal_bp.route("/citas/solicitar", methods=["GET", "POST"])
@login_required
def solicitar_cita() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    form = SolicitarCitaForm()
    vehiculos = PortalService.get_vehiculos(cliente)
    if form.validate_on_submit():
        if not any(v.id == form.vehiculo_id.data for v in vehiculos):
            flash("Vehículo inválido.", "danger")
            return render_template("portal/solicitar_cita.html", form=form, vehiculos=vehiculos)
        cita = Cita(
            cliente_id=cliente.id,
            vehiculo_id=form.vehiculo_id.data,
            fecha=form.fecha.data,
            hora=form.hora.data,
            descripcion=form.descripcion.data,
            estado="pendiente",
        )
        db.session.add(cita)
        try:
            safe_commit()
            logger.info("Cliente %s solicitó cita #%s", cliente.id, cita.id)
            flash("Cita solicitada. Te contactaremos para confirmarla.", "success")
            return redirect(url_for("portal.citas"))
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    return render_template("portal/solicitar_cita.html", form=form, vehiculos=vehiculos)


@portal_bp.route("/citas/<int:cita_id>/cancelar", methods=["POST"])
@login_required
def cancelar_cita(cita_id: int) -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    cita = Cita.query.filter_by(id=cita_id, cliente_id=cliente.id).first()
    if not cita:
        flash("Cita no encontrada", "danger")
        return redirect(url_for("portal.citas"))
    if cita.estado != "pendiente":
        flash("Solo se pueden cancelar citas pendientes", "warning")
        return redirect(url_for("portal.citas"))
    cita.estado = "cancelado"
    try:
        safe_commit()
        flash("Cita cancelada", "success")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("portal.citas"))


@portal_bp.route("/facturas")
@login_required
def facturas() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = PortalService.get_facturas(cliente)
    return render_template("portal/facturas.html", cliente=cliente, facturas=lista)


@portal_bp.route("/facturas/<int:factura_id>")
@login_required
def factura_detalle(factura_id: int) -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    factura = PortalService.get_factura(cliente, factura_id)
    if not factura:
        flash("Factura no encontrada", "danger")
        return redirect(url_for("portal.facturas"))
    config = ConfiguracionTaller.get_config()
    return render_template("portal/factura_detalle.html", factura=factura, config=config)


@portal_bp.route("/facturas/<int:factura_id>/pdf")
@login_required
def factura_pdf(factura_id: int) -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    factura = PortalService.get_factura(cliente, factura_id)
    if not factura:
        flash("Factura no encontrada", "danger")
        return redirect(url_for("portal.facturas"))
    try:
        from weasyprint import HTML
    except ImportError:
        flash("PDF no disponible temporalmente.", "warning")
        return redirect(url_for("portal.factura_detalle", factura_id=factura_id))
    config = ConfiguracionTaller.get_config()
    from flask import render_template as _rt
    html_str = _rt("facturas/pdf.html", factura=factura, config=config)
    try:
        pdf_bytes = HTML(string=html_str, base_url=request.host_url).write_pdf()
    except Exception:
        flash("No se pudo generar el PDF. Prueba la vista de impresión del navegador.", "warning")
        return redirect(url_for("portal.factura_detalle", factura_id=factura_id))
    import io
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"factura_{factura.numero}.pdf",
    )


@portal_bp.route("/pagos")
@login_required
def pagos() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = PortalService.get_pagos(cliente)
    return render_template("portal/pagos.html", cliente=cliente, pagos=lista)


@portal_bp.route("/ordenes")
@login_required
def ordenes() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = PortalService.get_ordenes(cliente)
    return render_template("portal/ordenes.html", cliente=cliente, ordenes=lista)


@portal_bp.route("/ordenes/<int:orden_id>")
@login_required
def orden_detalle(orden_id: int) -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    orden = next((o for o in PortalService.get_ordenes(cliente) if o.id == orden_id), None)
    if not orden:
        flash("Orden de trabajo no encontrada", "danger")
        return redirect(url_for("portal.ordenes"))
    return render_template("portal/orden_detalle.html", orden=orden)


@portal_bp.route("/historial")
@login_required
def historial() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = PortalService.get_historial(cliente)
    return render_template("portal/historial.html", cliente=cliente, registros=lista)


@portal_bp.route("/recordatorios")
@login_required
def recordatorios() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = RecordatorioService.get_para_cliente(cliente)
    return render_template("portal/recordatorios.html", cliente=cliente, recordatorios=lista)


@portal_bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil() -> Any:
    from services.image_service import ImageService, ImageError

    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    form = PerfilForm(obj=cliente)
    if form.validate_on_submit():
        cliente.nombre = form.nombre.data.strip()
        cliente.telefono = form.telefono.data.strip() if form.telefono.data else None
        cliente.direccion = form.direccion.data.strip() if form.direccion.data else None
        nuevo_correo = form.correo.data.strip() if form.correo.data else None
        if nuevo_correo and nuevo_correo != cliente.correo:
            otro = Cliente.query.filter(Cliente.correo == nuevo_correo, Cliente.id != cliente.id).first()
            if otro:
                flash("Ese correo ya está en uso.", "danger")
                return render_template("portal/perfil.html", form=form, cliente=cliente)
            cliente.correo = nuevo_correo
            current_user.correo = nuevo_correo
        if form.foto.data and getattr(form.foto.data, "filename", ""):
            try:
                nueva = ImageService.guardar(form.foto.data, "perfiles")
            except ImageError as e:
                flash(str(e), "danger")
                return render_template("portal/perfil.html", form=form, cliente=cliente)
            vieja = current_user.foto_path
            current_user.foto_path = nueva
            ImageService.eliminar(vieja)
        try:
            safe_commit()
            flash("Datos actualizados", "success")
            return redirect(url_for("portal.perfil"))
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    return render_template("portal/perfil.html", form=form, cliente=cliente)


@portal_bp.route("/perfil/password", methods=["POST"])
@login_required
def cambiar_password() -> Any:
    form = CambiarPasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.password_actual.data):
            flash("La contraseña actual no es correcta", "danger")
            return redirect(url_for("portal.perfil"))
        current_user.set_password(form.nueva_password.data)
        try:
            safe_commit()
            flash("Contraseña actualizada", "success")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "danger")
    return redirect(url_for("portal.perfil"))
