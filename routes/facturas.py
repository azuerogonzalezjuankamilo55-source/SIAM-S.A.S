import logging
from typing import Any
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf
from decorators import admin_required, staff_blueprint_guard

from models.cita import Cita
from models.servicio import Servicio
from models.factura import Factura
from models.orden_trabajo import OrdenTrabajo
from models.configuracion_taller import ConfiguracionTaller
from models.pago_factura import PagoFactura
from database.db import db
from services.factura_service import FacturaService, FacturaInput
from services.image_service import ImageService, ImageError
from forms import PagoForm, TallerConfigForm
from exceptions import BusinessRuleException, NotFoundException
from database.commit import safe_commit, json_success, json_error

logger = logging.getLogger("siam.routes.facturas")
facturas_bp = Blueprint("facturas", __name__, url_prefix="/facturas")
facturas_bp.before_request(staff_blueprint_guard)


@facturas_bp.route("/")
@login_required
def listar() -> Any:
    estado = request.args.get("estado")
    q = Factura.query
    if estado:
        q = q.filter(Factura.estado == estado)
    facturas = q.order_by(Factura.created_at.desc()).all()
    return render_template("facturas/listar.html", facturas=facturas)


@facturas_bp.route("/crear/<int:cita_id>", methods=["GET", "POST"])
@login_required
def crear(cita_id: int) -> Any:
    cita = db.get_or_404(Cita, cita_id)
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()

    if request.method == "POST":
        try:
            csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
            if csrf_token:
                validate_csrf(csrf_token)
            input_data = FacturaInput(
                cita_id=cita_id,
                servicio_ids=[int(s) for s in request.form.getlist("servicio_id")],
                precios=[Decimal(p or "0") for p in request.form.getlist("precio_unitario")],
                cantidades=[int(c or "1") for c in request.form.getlist("cantidad")],
                descuento=Decimal(request.form.get("descuento") or "0"),
                metodo_pago=request.form.get("metodo_pago", "Efectivo"),
                notas=request.form.get("notas", ""),
                orden_trabajo_id=None,
            )
            FacturaService.generar(input_data)
            logger.info("Factura creada para cita %s", cita_id)
            if request.is_json:
                return json_success(message="Factura generada exitosamente.")
            flash("Factura generada exitosamente", "success")
            return redirect(url_for("facturas.listar"))
        except (BusinessRuleException, NotFoundException) as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
            logger.warning("Error al crear factura: %s", e)
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
            logger.error("Error inesperado al crear factura: %s", e)

    return render_template("facturas/form.html", cita=cita, servicios=servicios,
                           config=ConfiguracionTaller.get_config())


@facturas_bp.route("/crear-desde-ot/<int:ot_id>", methods=["GET", "POST"])
@login_required
def crear_desde_ot(ot_id: int) -> Any:
    ot = db.get_or_404(OrdenTrabajo, ot_id)
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()

    if ot.cliente.citas:
        cita = ot.cliente.citas[0] if ot.cliente.citas else None
    else:
        cita = None

    if not cita:
        flash("La OT no tiene una cita asociada. Cree una cita primero.", "warning")
        return redirect(url_for("ordenes_trabajo.ver", id=ot_id))

    if request.method == "POST":
        try:
            input_data = FacturaInput(
                cita_id=cita.id,
                servicio_ids=[int(s) for s in request.form.getlist("servicio_id")],
                precios=[Decimal(p or "0") for p in request.form.getlist("precio_unitario")],
                cantidades=[int(c or "1") for c in request.form.getlist("cantidad")],
                descuento=Decimal(request.form.get("descuento") or "0"),
                metodo_pago=request.form.get("metodo_pago", "Efectivo"),
                notas=request.form.get("notas", ""),
                orden_trabajo_id=ot_id,
            )
            FacturaService.generar(input_data)
            logger.info("Factura creada desde OT %s", ot_id)
            if request.is_json:
                return json_success(message="Factura generada desde la orden de trabajo.")
            flash("Factura generada desde la orden de trabajo", "success")
            return redirect(url_for("facturas.listar"))
        except (BusinessRuleException, NotFoundException) as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
            logger.warning("Error al crear factura desde OT: %s", e)
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
            logger.error("Error inesperado al crear factura desde OT: %s", e)

    return render_template("facturas/form.html", cita=cita, servicios=servicios, ot=ot,
                           config=ConfiguracionTaller.get_config())


@facturas_bp.route("/ver/<int:id>")
@login_required
def ver(id: int) -> Any:
    factura = db.get_or_404(Factura, id)
    config = ConfiguracionTaller.get_config()
    return render_template("facturas/ver.html", factura=factura, config=config)


@facturas_bp.route("/pdf/<int:id>")
@login_required
def pdf(id: int) -> Any:
    try:
        from weasyprint import HTML
    except ImportError:
        flash("PDF no disponible: weasyprint no estÃ¡ instalado", "danger")
        return redirect(url_for("facturas.ver", id=id))

    factura = db.get_or_404(Factura, id)
    config = ConfiguracionTaller.get_config()
    html_str = render_template("facturas/pdf.html", factura=factura, config=config)
    try:
        pdf_bytes = HTML(string=html_str, base_url=request.host_url).write_pdf()
    except Exception:
        flash("Error generando PDF. Verifique la impresiÃ³n desde el navegador.", "warning")
        return redirect(url_for("facturas.ver", id=id))

    import io
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"factura_{factura.numero}.pdf",
    )


@facturas_bp.route("/pagar/<int:id>", methods=["GET", "POST"])
@login_required
def pagar(id: int) -> Any:
    factura = db.get_or_404(Factura, id)
    if factura.estado == "anulado":
        flash("No se puede pagar una factura anulada", "danger")
        return redirect(url_for("facturas.ver", id=id))

    form = PagoForm()
    if form.validate_on_submit():
        try:
            FacturaService.registrar_pago(
                factura_id=id,
                monto=form.monto.data,
                metodo_pago=form.metodo_pago.data,
                usuario_id=current_user.id,
                referencia=form.referencia.data or "",
                notas=form.notas.data or "",
            )
            logger.info("Pago registrado en factura %s", factura.numero)
            if request.is_json:
                return json_success(message="Pago registrado exitosamente.")
            flash("Pago registrado exitosamente", "success")
            return redirect(url_for("facturas.ver", id=id))
        except (BusinessRuleException, NotFoundException) as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
            logger.error("Error inesperado al registrar pago: %s", e)

    return render_template("facturas/pagar.html", factura=factura, form=form)


@facturas_bp.route("/anular/<int:id>", methods=["POST"])
@login_required
def anular(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        flash("Error de validaciÃ³n. Intenta de nuevo.", "danger")
        return redirect(url_for("facturas.ver", id=id))
    factura = db.get_or_404(Factura, id)
    if factura.monto_pagado > 0:
        if request.is_json:
            return json_error(message="No se puede anular: tiene pagos registrados")
        flash("No se puede anular: tiene pagos registrados", "danger")
        return redirect(url_for("facturas.ver", id=id))
    try:
        factura.estado = "anulado"
        safe_commit()
        logger.info("Factura %s anulada", factura.numero)
        if request.is_json:
            return json_success(message="Factura anulada.")
        flash("Factura anulada", "success")
        return redirect(url_for("facturas.listar"))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("facturas.ver", id=id))


@facturas_bp.route("/configuracion", methods=["GET", "POST"])
@login_required
@admin_required
def configuracion() -> Any:
    config = ConfiguracionTaller.get_config()
    form = TallerConfigForm(obj=config)
    if form.validate_on_submit():
        config.nombre_taller = form.nombre_taller.data
        config.nit = form.nit.data
        config.direccion = form.direccion.data
        config.telefono = form.telefono.data
        config.email = form.email.data
        config.regimen = form.regimen.data
        config.prefijo_factura = form.prefijo_factura.data
        config.resolucion_dian = form.resolucion_dian.data
        config.iva_porcentaje = form.iva_porcentaje.data

        if form.logo.data and hasattr(form.logo.data, "filename") and form.logo.data.filename:
            try:
                nueva_ruta = ImageService.guardar(form.logo.data, "logos")
            except ImageError as e:
                flash(str(e), "danger")
                return redirect(url_for("facturas.configuracion"))
            vieja = config.logo_path
            config.logo_path = nueva_ruta
            try:
                safe_commit()
            except Exception:
                ImageService.eliminar(nueva_ruta)
                raise
            ImageService.eliminar(vieja)

        try:
            safe_commit()
            logger.info("ConfiguraciÃ³n del taller actualizada")
            if request.is_json:
                return json_success(message="ConfiguraciÃ³n guardada.")
            flash("ConfiguraciÃ³n guardada", "success")
            return redirect(url_for("facturas.configuracion"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
            return redirect(url_for("facturas.configuracion"))

    return render_template("facturas/configuracion.html", form=form, config=config)


@facturas_bp.route("/configuracion/quitar-logo", methods=["POST"])
@login_required
@admin_required
def quitar_logo() -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        flash("Error de validaciÃ³n. Intenta de nuevo.", "danger")
        return redirect(url_for("facturas.configuracion"))
    config = ConfiguracionTaller.get_config()
    if config.logo_path:
        viejo = config.logo_path
        config.logo_path = None
        try:
            safe_commit()
            ImageService.eliminar(viejo)
            flash("Logo eliminado", "success")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    else:
        flash("No hay logo configurado", "warning")
    return redirect(url_for("facturas.configuracion"))


@facturas_bp.route("/eliminar-pago/<int:pago_id>", methods=["POST"])
@login_required
def eliminar_pago(pago_id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        flash("Error de validaciÃ³n. Intenta de nuevo.", "danger")
        return redirect(url_for("facturas.listar"))
    pago = db.get_or_404(PagoFactura, pago_id)
    factura_id = pago.factura_id
    try:
        db.session.delete(pago)
        factura = db.session.get(Factura, factura_id)
        if factura.monto_pagado <= 0:
            factura.estado = "pendiente"
        elif factura.monto_pagado < factura.total:
            factura.estado = "parcial"
        safe_commit()
        logger.info("Pago %s eliminado", pago_id)
        if request.is_json:
            return json_success(message="Pago eliminado.")
        flash("Pago eliminado", "success")
        return redirect(url_for("facturas.ver", id=factura_id))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
        return redirect(url_for("facturas.ver", id=factura_id))
