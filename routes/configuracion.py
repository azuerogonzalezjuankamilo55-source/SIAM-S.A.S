import logging
from typing import Any

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from database.commit import json_error, json_success, safe_commit
from database.db import db
from decorators import staff_blueprint_guard
from forms import (
    AparienciaForm,
    CitasConfigForm,
    EmpresaConfigForm,
    IAConfigForm,
    NotificacionesConfigForm,
)
from models import Usuario
from models.configuracion_taller import ConfiguracionTaller
from services.configuracion_service import ConfiguracionService
from services.image_service import ImageError, ImageService
from services.sede_service import SedeService

logger = logging.getLogger("siam.routes.configuracion")
configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")
configuracion_bp.before_request(staff_blueprint_guard)

SECCIONES_LECTURA = {"sedes", "archivos", "seguridad", "sistema"}


def _es_ajax() -> bool:
    """Detecta peticiones AJAX del JS (envía Accept: application/json)."""
    if request.mimetype == "application/json":
        return True
    return "application/json" in request.headers.get("Accept", "")


def _admin_o_403(seccion: str) -> Any | None:
    """Valida permisos de escritura: solo admin puede guardar."""
    if current_user.rol == "admin":
        return None
    if _es_ajax():
        return json_error("No tienes permisos de administrador.", 403)
    flash("No tienes permisos de administrador.", "danger")
    return redirect(url_for("configuracion.seccion", seccion=seccion))


def _errores_formulario(form) -> str:
    partes: list[str] = []
    for campo, errores in form.errors.items():
        etiqueta = getattr(form[campo], "label", None)
        nombre = etiqueta.text if etiqueta is not None else campo
        partes.append(f"{nombre}: {', '.join(errores)}")
    return " ".join(partes) or "Revisa los campos del formulario."


@configuracion_bp.route("/")
@login_required
def index() -> Any:
    return redirect(url_for("configuracion.seccion", seccion="empresa"))


@configuracion_bp.route("/<seccion>", methods=["GET", "POST"])
@login_required
def seccion(seccion: str) -> Any:
    if seccion not in ConfiguracionService.SECCIONES:
        abort(404)
    if seccion in SECCIONES_LECTURA and request.method == "POST":
        abort(405)

    config = ConfiguracionTaller.get_config()

    if seccion == "empresa":
        form = EmpresaConfigForm(obj=config)
        if request.method == "POST":
            bloqueo = _admin_o_403(seccion)
            if bloqueo:
                return bloqueo
            if form.validate_on_submit():
                if form.logo.data and getattr(form.logo.data, "filename", ""):
                    try:
                        nueva_ruta = ImageService.guardar(form.logo.data, "logos")
                    except ImageError as e:
                        if _es_ajax():
                            return json_error(str(e), 400)
                        flash(str(e), "danger")
                        return redirect(url_for("configuracion.seccion", seccion="empresa"))
                    vieja = config.logo_path
                    config.logo_path = nueva_ruta
                    try:
                        safe_commit()
                    except Exception:
                        ImageService.eliminar(nueva_ruta)
                        raise
                    ImageService.eliminar(vieja)
                try:
                    ConfiguracionService.aplicar(config, "empresa", form.data)
                    if _es_ajax():
                        return json_success(message="Configuración de empresa guardada.")
                    flash("Configuración de empresa guardada", "success")
                    return redirect(url_for("configuracion.seccion", seccion="empresa"))
                except Exception as e:
                    db.session.rollback()
                    if _es_ajax():
                        return json_error(message=str(e))
                    flash(str(e), "danger")
                    return redirect(url_for("configuracion.seccion", seccion="empresa"))
            if _es_ajax():
                return json_error(_errores_formulario(form), 400)
        return render_template(
            "configuracion/index.html", seccion="empresa", form=form, config=config,
            puede_editar=current_user.rol == "admin",
        )

    if seccion == "apariencia":
        form = AparienciaForm(obj=config)
        if request.method == "POST":
            bloqueo = _admin_o_403(seccion)
            if bloqueo:
                return bloqueo
            if form.validate_on_submit():
                try:
                    ConfiguracionService.aplicar(config, "apariencia", form.data)
                    if _es_ajax():
                        return json_success(message="Apariencia actualizada.")
                    flash("Apariencia actualizada", "success")
                    return redirect(url_for("configuracion.seccion", seccion="apariencia"))
                except Exception as e:
                    db.session.rollback()
                    if _es_ajax():
                        return json_error(message=str(e))
                    flash(str(e), "danger")
                    return redirect(url_for("configuracion.seccion", seccion="apariencia"))
            if _es_ajax():
                return json_error(_errores_formulario(form), 400)
        return render_template(
            "configuracion/index.html", seccion="apariencia", form=form, config=config,
            puede_editar=current_user.rol == "admin",
        )

    if seccion == "citas":
        form = CitasConfigForm(obj=config)
        if request.method == "POST":
            bloqueo = _admin_o_403(seccion)
            if bloqueo:
                return bloqueo
            if form.validate_on_submit():
                try:
                    ConfiguracionService.aplicar(config, "citas", form.data)
                    if _es_ajax():
                        return json_success(message="Configuración de citas guardada.")
                    flash("Configuración de citas guardada", "success")
                    return redirect(url_for("configuracion.seccion", seccion="citas"))
                except Exception as e:
                    db.session.rollback()
                    if _es_ajax():
                        return json_error(message=str(e))
                    flash(str(e), "danger")
                    return redirect(url_for("configuracion.seccion", seccion="citas"))
            if _es_ajax():
                return json_error(_errores_formulario(form), 400)
        return render_template(
            "configuracion/index.html", seccion="citas", form=form, config=config,
            puede_editar=current_user.rol == "admin",
        )

    if seccion == "notificaciones":
        form = NotificacionesConfigForm(obj=config)
        if request.method == "POST":
            bloqueo = _admin_o_403(seccion)
            if bloqueo:
                return bloqueo
            if form.validate_on_submit():
                try:
                    ConfiguracionService.aplicar(config, "notificaciones", form.data)
                    if _es_ajax():
                        return json_success(message="Configuración de notificaciones guardada.")
                    flash("Configuración de notificaciones guardada", "success")
                    return redirect(url_for("configuracion.seccion", seccion="notificaciones"))
                except Exception as e:
                    db.session.rollback()
                    if _es_ajax():
                        return json_error(message=str(e))
                    flash(str(e), "danger")
                    return redirect(url_for("configuracion.seccion", seccion="notificaciones"))
            if _es_ajax():
                return json_error(_errores_formulario(form), 400)
        return render_template(
            "configuracion/index.html", seccion="notificaciones", form=form, config=config,
            puede_editar=current_user.rol == "admin",
        )

    if seccion == "ia":
        form = IAConfigForm(obj=config)
        if request.method != "POST":
            form.ia_preguntas_sugeridas.data = "\n".join(ConfiguracionService.preguntas(config))
        if request.method == "POST":
            bloqueo = _admin_o_403(seccion)
            if bloqueo:
                return bloqueo
            if form.validate_on_submit():
                try:
                    ConfiguracionService.aplicar(config, "ia", form.data)
                    if _es_ajax():
                        return json_success(message="Configuración del asistente guardada.")
                    flash("Configuración del asistente guardada", "success")
                    return redirect(url_for("configuracion.seccion", seccion="ia"))
                except Exception as e:
                    db.session.rollback()
                    if _es_ajax():
                        return json_error(message=str(e))
                    flash(str(e), "danger")
                    return redirect(url_for("configuracion.seccion", seccion="ia"))
            if _es_ajax():
                return json_error(_errores_formulario(form), 400)
        return render_template(
            "configuracion/index.html", seccion="ia", form=form, config=config,
            puede_editar=current_user.rol == "admin",
        )

    if seccion == "sedes":
        return render_template(
            "configuracion/index.html", seccion="sedes", config=config,
            sedes=SedeService.listar(), puede_editar=current_user.rol == "admin",
        )

    if seccion == "archivos":
        datos_archivos = {
            "max_imagen_mb": current_app.config.get("FILE_MAX_IMAGE_MB", 5),
            "max_video_mb": current_app.config.get("FILE_MAX_VIDEO_MB", 100),
            "max_pdf_mb": current_app.config.get("FILE_MAX_PDF_MB", 15),
            "max_total_mb": round((current_app.config.get("MAX_CONTENT_LENGTH") or 0) / (1024 * 1024), 1),
            "formatos": "JPG, PNG, WebP",
        }
        return render_template(
            "configuracion/index.html", seccion="archivos", config=config,
            datos_archivos=datos_archivos, puede_editar=current_user.rol == "admin",
        )

    if seccion == "seguridad":
        usuarios = (
            Usuario.query.order_by(Usuario.rol, Usuario.nombre)
            .with_entities(Usuario.id, Usuario.nombre, Usuario.correo, Usuario.rol, Usuario.activo, Usuario.last_access_at)
            .all()
        )
        return render_template(
            "configuracion/index.html", seccion="seguridad", config=config,
            datos_seguridad=ConfiguracionService.datos_seguridad(),
            usuarios=usuarios, puede_editar=current_user.rol == "admin",
        )

    # seccion == "sistema"
    return render_template(
        "configuracion/index.html", seccion="sistema", config=config,
        datos_sistema=ConfiguracionService.datos_sistema(),
        puede_editar=current_user.rol == "admin",
    )


@configuracion_bp.route("/sistema/comprobar", methods=["POST"])
@login_required
def sistema_comprobar() -> Any:
    if current_user.rol != "admin":
        return json_error("No tienes permisos de administrador.", 403)
    resultados = ConfiguracionService.estado_sistema()
    return json_success(data={"resultados": resultados})


@configuracion_bp.route("/quitar-logo", methods=["POST"])
@login_required
def quitar_logo() -> Any:
    bloqueo = _admin_o_403("empresa")
    if bloqueo:
        return bloqueo
    try:
        from flask_wtf.csrf import validate_csrf

        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if _es_ajax():
            return json_error("Error de validación.", 400)
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("configuracion.seccion", seccion="empresa"))
    config = ConfiguracionTaller.get_config()
    if config.logo_path:
        viejo = config.logo_path
        config.logo_path = None
        try:
            safe_commit()
            ImageService.eliminar(viejo)
            if _es_ajax():
                return json_success(message="Logo eliminado.")
            flash("Logo eliminado", "success")
        except Exception as e:
            db.session.rollback()
            if _es_ajax():
                return json_error(message=str(e))
            flash(str(e), "danger")
    else:
        if _es_ajax():
            return json_error("No hay logo configurado.", 400)
        flash("No hay logo configurado", "warning")
    return redirect(url_for("configuracion.seccion", seccion="empresa"))
