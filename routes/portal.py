import logging
import os
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user

from models.cliente import Cliente
from models.cita import Cita
from models.servicio import Servicio
from models.adjunto import Adjunto
from models.configuracion_taller import ConfiguracionTaller
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import SolicitarCitaForm, PerfilForm, CambiarPasswordForm
from services.notification_service import NotificationService
from services.storage_service import AdjuntoService
from services.portal_service import PortalService
from services.recordatorio_service import RecordatorioService

from decorators import STAFF_ROLES

logger = logging.getLogger("siam.routes.portal")
portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


def _portal_guard():
    """El portal es área del cliente: el personal del taller se envía al dashboard."""
    if current_user.is_authenticated and current_user.rol in STAFF_ROLES:
        return redirect(url_for("dashboard.index"))
    return None


portal_bp.before_request(_portal_guard)


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
    from services.sede_service import SedeService

    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    form = SolicitarCitaForm()
    vehiculos = PortalService.get_vehiculos(cliente)
    sedes = SedeService.listar()
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()
    form.sede_id.choices = [(s["id"], s["nombre"]) for s in sedes]
    form.servicio_id.choices = [(sv.id, sv.nombre) for sv in servicios]
    if form.validate_on_submit():
        if not any(v.id == form.vehiculo_id.data for v in vehiculos):
            flash("Vehículo inválido.", "danger")
            return render_template(
                "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
            )
        sede_id = form.sede_id.data
        if not any(s["id"] == sede_id for s in sedes):
            flash("Sede inválida.", "danger")
            return render_template(
                "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
            )
        servicio_id = form.servicio_id.data
        if servicio_id and not any(sv.id == servicio_id for sv in servicios):
            flash("Servicio inválido.", "danger")
            return render_template(
                "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
            )
        if SedeService.sede_ocupada(sede_id, form.fecha.data, form.hora.data):
            flash("Ese horario ya está reservado en la sede elegida. Elige otro.", "warning")
            return render_template(
                "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
            )
        from datetime import datetime, timedelta
        from models.configuracion_taller import ConfiguracionTaller
        from services.configuracion_service import ConfiguracionService

        config_citas = ConfiguracionTaller.get_config()
        if config_citas.citas_min_anticipacion_horas and config_citas.citas_min_anticipacion_horas > 0:
            cita_dt = datetime.combine(form.fecha.data, form.hora.data)
            if cita_dt < datetime.now() + timedelta(hours=config_citas.citas_min_anticipacion_horas):
                flash("La cita debe programarse con la anticipación mínima configurada.", "warning")
                return render_template(
                    "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
                )
        if not ConfiguracionService.hora_en_intervalo(form.hora.data, config_citas.citas_intervalo_min):
            flash("La hora elegida no se ajusta al intervalo de citas del taller.", "warning")
            return render_template(
                "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
            )
        cita = Cita(
            cliente_id=cliente.id,
            vehiculo_id=form.vehiculo_id.data,
            sede_id=sede_id,
            servicio_id=servicio_id or None,
            fecha=form.fecha.data,
            hora=form.hora.data,
            descripcion=form.descripcion.data,
            estado="pendiente",
        )
        db.session.add(cita)
        try:
            safe_commit()
            logger.info("Cliente %s solicitó cita #%s", cliente.id, cita.id)
            archivos = request.files.getlist("adjuntos")
            for archivo in archivos:
                if archivo and archivo.filename:
                    try:
                        AdjuntoService.crear(
                            current_user, "documento", archivo,
                            entidad_tipo="cita", entidad_id=cita.id,
                            subcarpeta="citas",
                        )
                    except Exception as e:
                        logger.warning("Adjunto de cita no se guardó: %s", e)
            sede_nombre = next((s["nombre"] for s in sedes if s["id"] == sede_id), "")
            NotificationService.notify_staff(
                "cita",
                "Nueva solicitud de cita",
                f"{cliente.nombre} solicitó una cita en {sede_nombre} para el {cita.fecha.strftime('%d/%m/%Y')} a las {cita.hora.strftime('%H:%M')}.",
                url_for("citas.listar"),
            )
            NotificationService.notify(
                current_user.id,
                "cita",
                "Cita solicitada",
                f"Tu solicitud para el {cita.fecha.strftime('%d/%m/%Y')} a las {cita.hora.strftime('%H:%M')} está pendiente de confirmación.",
                url_for("portal.citas"),
            )
            flash("Cita solicitada. Te contactaremos para confirmarla.", "success")
            return redirect(url_for("portal.citas"))
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    return render_template(
        "portal/solicitar_cita.html", form=form, vehiculos=vehiculos, sedes=sedes, servicios=servicios
    )


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
    from datetime import datetime, timedelta
    from models.configuracion_taller import ConfiguracionTaller

    config_citas = ConfiguracionTaller.get_config()
    limite_horas = config_citas.citas_cancelar_limite_horas or 0
    if limite_horas > 0:
        cita_dt = datetime.combine(cita.fecha, cita.hora)
        if cita_dt - datetime.now() < timedelta(hours=limite_horas):
            flash("Ya no puedes cancelar esta cita: se acerca su horario. Contacta al taller.", "warning")
            return redirect(url_for("portal.citas"))
    cita.estado = "cancelado"
    try:
        safe_commit()
        NotificationService.notify_staff(
            "cita",
            "Cita cancelada por el cliente",
            f"{cliente.nombre} canceló su cita del {cita.fecha.strftime('%d/%m/%Y')} a las {cita.hora.strftime('%H:%M')}.",
            url_for("citas.listar"),
        )
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


@portal_bp.route("/cotizaciones")
@login_required
def cotizaciones() -> Any:
    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    from models.cotizacion import ESTADOS_COTIZACION_LABELS
    from services.cotizacion_service import CotizacionService
    lista = CotizacionService.get_para_cliente(cliente.id)
    return render_template("portal/cotizaciones.html", cliente=cliente, cotizaciones=lista, labels=ESTADOS_COTIZACION_LABELS)


@portal_bp.route("/cotizaciones/<int:cotizacion_id>")
@login_required
def cotizacion_detalle(cotizacion_id: int) -> Any:
    from models.cotizacion import Cotizacion, ESTADOS_COTIZACION_LABELS
    from services.cotizacion_service import CotizacionService

    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    cotizacion = next((c for c in CotizacionService.get_para_cliente(cliente.id) if c.id == cotizacion_id), None)
    if not cotizacion:
        flash("Cotización no encontrada", "danger")
        return redirect(url_for("portal.cotizaciones"))
    return render_template("portal/cotizacion_detalle.html", cotizacion=cotizacion, labels=ESTADOS_COTIZACION_LABELS)


@portal_bp.route("/cotizaciones/<int:cotizacion_id>/responder/<estado>", methods=["POST"])
@login_required
def cotizacion_responder(cotizacion_id: int, estado: str) -> Any:
    from services.cotizacion_service import CotizacionService

    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    if estado not in ("aprobada", "rechazada"):
        flash("Acción no válida.", "danger")
        return redirect(url_for("portal.cotizaciones"))
    try:
        cotizacion = next((c for c in CotizacionService.get_para_cliente(cliente.id) if c.id == cotizacion_id), None)
        if not cotizacion:
            flash("Cotización no encontrada", "danger")
            return redirect(url_for("portal.cotizaciones"))
        if cotizacion.estado != "pendiente":
            flash("Esta cotización ya fue respondida.", "warning")
            return redirect(url_for("portal.cotizacion_detalle", cotizacion_id=cotizacion_id))
        CotizacionService.cambiar_estado(cotizacion_id, estado)
        from services.notification_service import NotificationService
        if estado == "aprobada":
            NotificationService.notify_staff(
                "cotizacion",
                "Cotización aprobada por el cliente",
                f"El cliente aprobó la cotización {cotizacion.numero}.",
                url_for("cotizaciones.ver", id=cotizacion.id),
            )
        else:
            NotificationService.notify_staff(
                "cotizacion",
                "Cotización rechazada",
                f"El cliente rechazó la cotización {cotizacion.numero}.",
                url_for("cotizaciones.ver", id=cotizacion.id),
            )
        flash("Respuesta registrada. Gracias.", "success")
        return redirect(url_for("portal.cotizacion_detalle", cotizacion_id=cotizacion_id))
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("portal.cotizaciones"))


@portal_bp.route("/garantias")
@login_required
def garantias() -> Any:
    from services.garantia_service import GarantiaService

    cliente = _cliente_actual()
    if not cliente:
        return redirect(url_for("portal.index"))
    lista = GarantiaService.get_para_cliente(cliente.id)
    return render_template("portal/garantias.html", cliente=cliente, garantias=lista)


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


@portal_bp.route("/documentos")
@login_required
def documentos() -> Any:
    adjuntos = AdjuntoService.listar(current_user.id)
    return render_template("portal/documentos.html", adjuntos=adjuntos)


@portal_bp.route("/documentos/adjuntar", methods=["POST"])
@login_required
def adjuntar_documento() -> Any:
    from services.storage_service import FileService, FileError

    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        flash("Selecciona un archivo.", "warning")
        return redirect(url_for("portal.documentos"))
    try:
        tipo = FileService.detectar_tipo(archivo.filename, getattr(archivo, "mimetype", None)) or "documento"
        adj = AdjuntoService.crear(current_user, tipo, archivo, subcarpeta="documentos")
        logger.info("Cliente %s adjuntó documento %s", current_user.id, adj.id)
        flash("Documento adjuntado correctamente.", "success")
    except FileError as e:
        flash(str(e), "danger")
    except Exception as e:
        logger.error("Error adjuntando documento: %s", e)
        flash("No se pudo guardar el archivo.", "danger")
    return redirect(url_for("portal.documentos"))


@portal_bp.route("/documentos/eliminar/<int:adjunto_id>", methods=["POST"])
@login_required
def eliminar_documento(adjunto_id: int) -> Any:
    if AdjuntoService.eliminar(current_user.id, adjunto_id):
        flash("Documento eliminado.", "success")
    else:
        flash("Documento no encontrado.", "danger")
    return redirect(url_for("portal.documentos"))


@portal_bp.route("/documentos/descargar/<int:adjunto_id>")
@login_required
def descargar_documento(adjunto_id: int) -> Any:
    from services.storage_service import FileService

    adj = Adjunto.query.filter_by(id=adjunto_id, usuario_id=current_user.id).first()
    if not adj:
        flash("Documento no encontrado.", "danger")
        return redirect(url_for("portal.documentos"))
    ruta = FileService._ruta_abs(adj.path)
    if not ruta or not os.path.isfile(ruta):
        flash("El archivo ya no existe.", "warning")
        return redirect(url_for("portal.documentos"))
    return send_file(ruta, as_attachment=True, download_name=adj.nombre_original, mimetype=adj.mime)
