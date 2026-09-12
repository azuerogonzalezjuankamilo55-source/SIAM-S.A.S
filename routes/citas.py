import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from models.cita import Cita, ESTADOS_CITA
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.mecanico import Mecanico
from models.servicio import Servicio
from database.db import db
from database.commit import safe_commit, json_success, json_error
from forms import CitaForm
from services.notification_service import NotificationService
from services.sede_service import SedeService
from services.vehiculo_service import VehiculoService
from services.ubicacion_service import UbicacionService
from decorators import staff_blueprint_guard, roles_required

logger = logging.getLogger("siam.routes.citas")
citas_bp = Blueprint("citas", __name__, url_prefix="/citas")
citas_bp.before_request(staff_blueprint_guard)


def _opciones_cita_form(form: CitaForm) -> tuple[list, list, list, list[dict], list]:
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    vehiculos = Vehiculo.query.order_by(Vehiculo.placa).all()
    mecanicos = Mecanico.query.filter_by(activo=True).order_by(Mecanico.nombre).all()
    sedes = SedeService.listar()
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()
    form.sede_id.choices = [(s["id"], s["nombre"]) for s in sedes]
    form.servicio_id.choices = [(sv.id, sv.nombre) for sv in servicios]
    return clientes, vehiculos, mecanicos, sedes, servicios


@citas_bp.route("/")
@login_required
def listar() -> Any:
    citas = Cita.query.order_by(Cita.fecha.desc(), Cita.hora.desc()).all()
    return render_template("citas/listar.html", citas=citas)


@citas_bp.route("/crear", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def crear() -> Any:
    form = CitaForm()
    clientes, vehiculos, mecanicos, sedes, servicios = _opciones_cita_form(form)
    if form.validate_on_submit():
        if form.sede_id.data and SedeService.sede_ocupada(form.sede_id.data, form.fecha.data, form.hora.data):
            if request.is_json:
                return json_error("Ese horario ya está reservado en la sede elegida.", 400)
            flash("Ese horario ya está reservado en la sede elegida. Elige otro.", "warning")
            return render_template("citas/form.html", form=form, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)
        from models.configuracion_taller import ConfiguracionTaller
        from datetime import datetime, timedelta
        from services.configuracion_service import ConfiguracionService

        config_citas = ConfiguracionTaller.get_config()
        if config_citas.citas_min_anticipacion_horas and config_citas.citas_min_anticipacion_horas > 0:
            cita_dt = datetime.combine(form.fecha.data, form.hora.data)
            if cita_dt < datetime.now() + timedelta(hours=config_citas.citas_min_anticipacion_horas):
                if request.is_json:
                    return json_error("La cita debe programarse con anticipación.", 400)
                flash("La cita debe programarse con la anticipación mínima configurada.", "warning")
                return render_template("citas/form.html", form=form, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)
        if not ConfiguracionService.hora_en_intervalo(form.hora.data, config_citas.citas_intervalo_min):
            if request.is_json:
                return json_error("La hora debe alinearse al intervalo de citas configurado.", 400)
            flash("La hora elegida no se ajusta al intervalo de citas configurado.", "warning")
            return render_template("citas/form.html", form=form, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)
        try:
            cita = Cita(
                cliente_id=form.cliente_id.data,
                vehiculo_id=form.vehiculo_id.data,
                mecanico_id=form.mecanico_id.data or None,
                sede_id=form.sede_id.data or None,
                servicio_id=form.servicio_id.data or None,
                fecha=form.fecha.data,
                hora=form.hora.data,
                descripcion=form.descripcion.data,
            )
            db.session.add(cita)
            safe_commit()
            logger.info("Cita creada: #%s para cliente %s", cita.id, cita.cliente_id)
            NotificationService.notify_cliente(
                cita.cliente_id,
                "cita",
                "Cita agendada",
                f"Tienes una cita para el {cita.fecha.strftime('%d/%m/%Y')} a las {cita.hora.strftime('%H:%M')}.",
                url_for("portal.citas"),
            )
            if request.is_json:
                return json_success(message="Creada correctamente.")
            flash("Cita agendada", "success")
            return redirect(url_for("citas.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("citas/form.html", form=form, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)


@citas_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def editar(id: int) -> Any:
    cita = db.get_or_404(Cita, id)
    form = CitaForm(obj=cita)
    clientes, vehiculos, mecanicos, sedes, servicios = _opciones_cita_form(form)
    if form.validate_on_submit():
        if form.sede_id.data and SedeService.sede_ocupada(
            form.sede_id.data, form.fecha.data, form.hora.data, cita_excluida_id=cita.id
        ):
            if request.is_json:
                return json_error("Ese horario ya está reservado en la sede elegida.", 400)
            flash("Ese horario ya está reservado en la sede elegida. Elige otro.", "warning")
            return render_template("citas/form.html", form=form, cita=cita, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)
        from models.configuracion_taller import ConfiguracionTaller
        from services.configuracion_service import ConfiguracionService

        if not ConfiguracionService.hora_en_intervalo(
            form.hora.data, ConfiguracionTaller.get_config().citas_intervalo_min
        ):
            if request.is_json:
                return json_error("La hora debe alinearse al intervalo de citas configurado.", 400)
            flash("La hora elegida no se ajusta al intervalo de citas configurado.", "warning")
            return render_template("citas/form.html", form=form, cita=cita, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)
        try:
            form.populate_obj(cita)
            safe_commit()
            logger.info("Cita actualizada: #%s", cita.id)
            if request.is_json:
                return json_success(message="Actualizada correctamente.")
            flash("Cita actualizada", "success")
            return redirect(url_for("citas.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(message=str(e))
            flash(str(e), "danger")
    return render_template("citas/form.html", form=form, cita=cita, clientes=clientes, vehiculos=vehiculos, mecanicos=mecanicos, sedes=sedes, servicios=servicios)


@citas_bp.route("/cambiar-estado/<int:id>/<estado>", methods=["POST"])
@login_required
@roles_required("admin", "recepcion")
def cambiar_estado(id: int, estado: str) -> Any:
    # Compatibilidad con estados legados de la versión anterior.
    estado = {"completado": "entregada", "en_proceso": "en_revision"}.get(estado, estado)
    try:
        cita = db.get_or_404(Cita, id)
        if estado in ESTADOS_CITA:
            cita.estado = estado
            if estado in ("entregada", "cancelado"):
                # Cita finalizada: detener el intercambio de ubicación en vivo.
                try:
                    UbicacionService.detener(cita.cliente_id, cita.id)
                except Exception as e:
                    logger.warning("No se pudo limpiar ubicaciones de cita %s: %s", id, e)
            safe_commit()
            if estado == "entregada":
                try:
                    from services.historial_service import HistorialService
                    HistorialService.registrar_desde_cita(cita, current_user.id if current_user.is_authenticated else None)
                except Exception as e:
                    logger.warning("No se pudo registrar historial de cita %s: %s", id, e)
            mensajes_estado = {
                "confirmada": ("Cita confirmada", f"Tu cita del {cita.fecha.strftime('%d/%m/%Y')} fue confirmada. ¡Te esperamos!"),
                "en_revision": ("Vehículo en revisión", f"Tu vehículo está siendo revisado (cita del {cita.fecha.strftime('%d/%m/%Y')})."),
                "en_reparacion": ("Vehículo en reparación", f"Tu vehículo entró en reparación (cita del {cita.fecha.strftime('%d/%m/%Y')})."),
                "lista": ("Vehículo listo", f"Tu vehículo está listo para recoger (cita del {cita.fecha.strftime('%d/%m/%Y')})."),
                "entregada": ("Servicio entregado", f"Tu vehículo fue entregado. Gracias por tu visita del {cita.fecha.strftime('%d/%m/%Y')}."),
                "cancelado": ("Cita cancelada", f"Tu cita del {cita.fecha.strftime('%d/%m/%Y')} fue cancelada por el taller."),
            }
            if estado in mensajes_estado:
                try:
                    NotificationService.notify_cliente(
                        cita.cliente_id,
                        "cita",
                        mensajes_estado[estado][0],
                        mensajes_estado[estado][1],
                        url_for("portal.citas"),
                    )
                except Exception as e:
                    logger.warning("No se pudo notificar el cambio de estado de la cita %s: %s", id, e)
            logger.info("Cita #%s cambió a estado: %s", id, estado)
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(message=str(e))
        flash(str(e), "danger")
    return redirect(url_for("citas.listar"))


@citas_bp.route("/obtener-vehiculos/<int:cliente_id>")
@login_required
@roles_required("admin", "recepcion")
def obtener_vehiculos(cliente_id: int) -> Any:
    return jsonify(VehiculoService.listar_para_select(cliente_id))
