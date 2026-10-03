import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import validate_csrf

from models.cliente import Cliente
from database.db import db
from forms import ClienteForm
from database.commit import safe_commit, json_success, json_error
from decorators import staff_blueprint_guard, roles_required
from services.notification_service import NotificationService

logger = logging.getLogger("siam.routes.clientes")
clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")
clientes_bp.before_request(staff_blueprint_guard)

#: Avisos rápidos que el taller envía al cliente sobre su servicio.
AVISOS_SERVICIO = (
    "Tu vehículo ya está siendo revisado por el mecánico.",
    "Tu servicio ha sido actualizado.",
    "Tu vehículo está listo para entrega.",
)


@clientes_bp.route("/")
@login_required
@roles_required("admin", "recepcion")
def listar() -> Any:
    clientes = Cliente.query.order_by(Cliente.created_at.desc()).all()
    return render_template(
        "clientes/listar.html", clientes=clientes, avisos_servicio=AVISOS_SERVICIO
    )


@clientes_bp.route("/crear", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def crear() -> Any:
    form = ClienteForm()
    if form.validate_on_submit():
        cliente = Cliente(
            nombre=form.nombre.data.strip(),
            telefono=form.telefono.data.strip() if form.telefono.data else None,
            correo=form.correo.data.strip() if form.correo.data else None,
            direccion=form.direccion.data.strip() if form.direccion.data else None,
            cedula=form.cedula.data.strip() if form.cedula.data else None,
        )
        db.session.add(cliente)
        try:
            safe_commit()
            logger.info("Cliente creado: %s", cliente.nombre)
            if request.is_json:
                return jsonify({"success": True, "message": "Cliente creado exitosamente"})
            flash("Cliente creado exitosamente", "success")
            return redirect(url_for("clientes.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("clientes/form.html", form=form)
    return render_template("clientes/form.html", form=form)


@clientes_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "recepcion")
def editar(id: int) -> Any:
    cliente = db.get_or_404(Cliente, id)
    form = ClienteForm(obj=cliente)
    if form.validate_on_submit():
        form.populate_obj(cliente)
        try:
            safe_commit()
            logger.info("Cliente actualizado: %s", cliente.nombre)
            if request.is_json:
                return jsonify({"success": True, "message": "Cliente actualizado"})
            flash("Cliente actualizado", "success")
            return redirect(url_for("clientes.listar"))
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return json_error(str(e))
            flash(str(e), "danger")
            return render_template("clientes/form.html", form=form, cliente=cliente)
    return render_template("clientes/form.html", form=form, cliente=cliente)


@clientes_bp.route("/eliminar/<int:id>", methods=["POST"])
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
        return redirect(url_for("clientes.listar"))
    cliente = db.get_or_404(Cliente, id)
    db.session.delete(cliente)
    try:
        safe_commit()
        logger.info("Cliente eliminado: %s", cliente.nombre)
        if request.is_json:
            return jsonify({"success": True})
        flash("Cliente eliminado", "success")
        return redirect(url_for("clientes.listar"))
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return json_error(str(e))
        flash(str(e), "danger")
        return redirect(url_for("clientes.listar"))


# ------------------------------------------------ comunicación admin -> cliente


@clientes_bp.route("/<int:id>/notificar", methods=["POST"])
@login_required
@roles_required("admin", "recepcion")
def notificar(id: int) -> Any:
    """Envía una comunicación al portal de un cliente concreto.

    Reutiliza `NotificationService.notify_cliente`, que persiste una fila en
    `notificaciones` para el usuario del cliente: aparece en su campana y en
    su área de comunicaciones. No es mensajería: es un aviso de servicio.
    """
    try:
        csrf_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if csrf_token:
            validate_csrf(csrf_token)
    except Exception:
        if request.is_json:
            return jsonify({"error": "CSRF inválido"}), 403
        flash("Error de validación. Intenta de nuevo.", "danger")
        return redirect(url_for("clientes.listar"))

    cliente = db.get_or_404(Cliente, id)
    data = request.get_json(silent=True) or request.form
    titulo = (data.get("titulo") or "").strip()[:200]
    mensaje = (data.get("mensaje") or "").strip()[:1000]

    if not mensaje:
        if request.is_json:
            return json_error("Escribe el mensaje para el cliente.", status=400)
        flash("Escribe el mensaje para el cliente.", "danger")
        return redirect(url_for("clientes.listar"))

    if not titulo:
        titulo = "Actualización de tu servicio"

    creada = NotificationService.notify_cliente(
        cliente.id,
        "orden",
        titulo,
        mensaje,
        url_for("portal.index"),
        commit=False,
    )
    if creada is None:
        # Sin usuario vinculado no hay campana donde avisar: se le dice al taller
        # en vez de aparentar que el cliente fue notificado.
        if request.is_json:
            return json_error(
                "Este cliente no tiene una cuenta asociada, así que no puede recibir el aviso.",
                status=400,
            )
        flash(
            "Este cliente no tiene una cuenta asociada, así que no puede recibir el aviso.",
            "warning",
        )
        return redirect(url_for("clientes.listar"))

    try:
        safe_commit()
    except Exception:
        db.session.rollback()
        logger.exception("No se pudo notificar al cliente %s", cliente.id)
        if request.is_json:
            return json_error("No se pudo enviar la comunicación.", status=500)
        flash("No se pudo enviar la comunicación.", "danger")
        return redirect(url_for("clientes.listar"))

    logger.info("Comunicación enviada al cliente %s por %s", cliente.id, getattr(current_user, "nombre", "personal"))
    if request.is_json:
        return json_success({"cliente_id": cliente.id}, "Comunicación enviada.")
    flash(f"Comunicación enviada a {cliente.nombre}.", "success")
    return redirect(url_for("clientes.listar"))
