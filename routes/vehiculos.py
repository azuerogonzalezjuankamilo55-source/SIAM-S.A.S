import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf

from models.vehiculo import Vehiculo
from models.cliente import Cliente
from models.historial_vehiculo import HistorialVehiculo, TIPOS_HISTORIAL, TIPOS_HISTORIAL_LABELS
from models.historial_foto import HistorialFoto, TIPOS_FOTO_HISTORIAL, TIPOS_FOTO_HISTORIAL_LABELS
from database.db import db
from forms import VehiculoForm
from database.commit import safe_commit, json_success, json_error
from services.historial_service import HistorialService
from services.image_service import ImageService, ImageError
from decorators import staff_blueprint_guard, roles_required

logger = logging.getLogger("siam.routes.vehiculos")
vehiculos_bp = Blueprint("vehiculos", __name__, url_prefix="/vehiculos")
vehiculos_bp.before_request(staff_blueprint_guard)


@vehiculos_bp.route("/")
@login_required
def listar() -> Any:
    vehiculos = Vehiculo.query.order_by(Vehiculo.created_at.desc()).all()
    return render_template("vehiculos/listar.html", vehiculos=vehiculos)


@vehiculos_bp.route("/historial/<int:vehiculo_id>", methods=["GET", "POST"])
@login_required
def historial(vehiculo_id: int) -> Any:
    vehiculo = db.get_or_404(Vehiculo, vehiculo_id)
    if request.method == "POST":
        tipo = request.form.get("tipo", "observacion")
        descripcion = request.form.get("descripcion", "").strip()
        kilometraje = request.form.get("kilometraje") or None
        if not descripcion:
            flash("La descripción es obligatoria", "danger")
        else:
            try:
                HistorialService.registrar(
                    vehiculo_id=vehiculo.id,
                    tipo=tipo if tipo in TIPOS_HISTORIAL else "observacion",
                    descripcion=descripcion,
                    kilometraje=int(kilometraje) if kilometraje else None,
                    creado_por=current_user.id if current_user.is_authenticated else None,
                )
                logger.info("Historial manual agregado al vehículo %s", vehiculo.placa)
                flash("Registro de historial agregado", "success")
            except Exception as e:
                db.session.rollback()
                flash(str(e), "danger")
        return redirect(url_for("vehiculos.historial", vehiculo_id=vehiculo.id))

    registros = HistorialService.get_historial_vehiculo(vehiculo.id)
    resumen = HistorialService.get_resumen(vehiculo.id)
    mantenimientos = HistorialService.get_proximos_mantenimientos(vehiculo.id)
    tipos_colores = {
        "cita": "info",
        "factura": "primary",
        "reparacion": "danger",
        "mantenimiento": "success",
        "cambio_aceite": "warning",
        "cambio_frenos": "warning",
        "alineacion": "secondary",
        "balanceo": "secondary",
        "llantas": "secondary",
        "bateria": "secondary",
        "revision": "success",
        "fotografia": "dark",
        "observacion": "light",
        "diagnostico": "info",
    }
    return render_template(
        "vehiculos/historial.html",
        vehiculo=vehiculo,
        registros=registros,
        resumen=resumen,
        mantenimientos=mantenimientos,
        tipos=TIPOS_HISTORIAL,
        tipos_labels=TIPOS_HISTORIAL_LABELS,
        tipos_colores=tipos_colores,
        tipos_foto=TIPOS_FOTO_HISTORIAL,
        tipos_foto_labels=TIPOS_FOTO_HISTORIAL_LABELS,
    )


@vehiculos_bp.route("/historial/<int:historial_id>/fotos/agregar", methods=["POST"])
@login_required
def agregar_foto_historial(historial_id: int) -> Any:
    registro = db.get_or_404(HistorialVehiculo, historial_id)
    archivo = request.files.get("foto")
    tipo = request.form.get("tipo", "antes")
    descripcion = request.form.get("descripcion", "").strip()
    if tipo not in TIPOS_FOTO_HISTORIAL:
        flash("Tipo de foto inválido", "danger")
        return redirect(url_for("vehiculos.historial", vehiculo_id=registro.vehiculo_id))
    if not archivo or not getattr(archivo, "filename", ""):
        flash("Selecciona una imagen", "danger")
        return redirect(url_for("vehiculos.historial", vehiculo_id=registro.vehiculo_id))
    try:
        ruta = ImageService.guardar(archivo, "historial")
    except ImageError as e:
        flash(str(e), "danger")
        return redirect(url_for("vehiculos.historial", vehiculo_id=registro.vehiculo_id))
    db.session.add(HistorialFoto(
        historial_vehiculo_id=registro.id,
        tipo=tipo,
        path=ruta,
        descripcion=descripcion or None,
    ))
    registro.tipo = "fotografia" if registro.tipo == "observacion" else registro.tipo
    try:
        safe_commit()
        logger.info("Foto %s agregada a historial %s", tipo, registro.id)
        if request.is_json:
            return json_success(message="Foto agregada.")
        flash("Foto agregada al historial", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e))
        flash(str(e), "danger")
    return redirect(url_for("vehiculos.historial", vehiculo_id=registro.vehiculo_id))


@vehiculos_bp.route("/historial/fotos/eliminar/<int:foto_id>", methods=["POST"])
@login_required
def eliminar_foto_historial(foto_id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return json_error(message="CSRF inválido"), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("vehiculos.listar"))
    foto = db.get_or_404(HistorialFoto, foto_id)
    vehiculo_id = foto.historial.vehiculo_id
    ruta = foto.path
    db.session.delete(foto)
    try:
        safe_commit()
        ImageService.eliminar(ruta)
        if request.is_json:
            return json_success(message="Foto eliminada.")
        flash("Foto eliminada", "success")
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e))
        flash(str(e), "danger")
    return redirect(url_for("vehiculos.historial", vehiculo_id=vehiculo_id))


@vehiculos_bp.route("/crear", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def crear() -> Any:
    form = VehiculoForm()
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    if form.validate_on_submit():
        vehiculo = Vehiculo(
            cliente_id=form.cliente_id.data,
            marca=form.marca.data,
            modelo=form.modelo.data,
            anio=form.anio.data,
            placa=form.placa.data,
            vin=form.vin.data,
            color=form.color.data,
        )
        db.session.add(vehiculo)
        try:
            safe_commit()
            logger.info("Vehículo registrado: %s %s", vehiculo.marca, vehiculo.placa)
            if request.is_json:
                return jsonify({"success": True, "message": "Vehículo registrado"})
            flash("Vehículo registrado", "success")
            return redirect(url_for("vehiculos.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("vehiculos/form.html", form=form, clientes=clientes)
    return render_template("vehiculos/form.html", form=form, clientes=clientes)


@vehiculos_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def editar(id: int) -> Any:
    vehiculo = db.get_or_404(Vehiculo, id)
    form = VehiculoForm(obj=vehiculo)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    if form.validate_on_submit():
        form.populate_obj(vehiculo)
        try:
            safe_commit()
            logger.info("Vehículo actualizado: %s", vehiculo.placa)
            if request.is_json:
                return jsonify({"success": True, "message": "Vehículo actualizado"})
            flash("Vehículo actualizado", "success")
            return redirect(url_for("vehiculos.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("vehiculos/form.html", form=form, vehiculo=vehiculo, clientes=clientes)
    return render_template("vehiculos/form.html", form=form, vehiculo=vehiculo, clientes=clientes)


@vehiculos_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
@roles_required("admin")
def eliminar(id: int) -> Any:
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return jsonify({"error": "CSRF inválido"}), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("vehiculos.listar"))
    vehiculo = db.get_or_404(Vehiculo, id)
    db.session.delete(vehiculo)
    try:
        safe_commit()
        logger.info("Vehículo eliminado: %s", vehiculo.placa)
        if request.is_json:
            return jsonify({"success": True})
        flash("Vehículo eliminado", "success")
        return redirect(url_for("vehiculos.listar"))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e))
        flash(str(e), "danger")
        return redirect(url_for("vehiculos.listar"))
