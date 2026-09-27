import logging
from typing import Any

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError

from models import Usuario, Cliente
from database.db import db
from forms import LoginForm, RegisterForm, AdminRegisterForm
from database.commit import safe_commit, json_success, json_error

logger = logging.getLogger("siam.routes.auth")
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class RegistroError(Exception):
    """Error de dominio del registro con mensaje seguro para el usuario."""

    def __init__(self, mensaje: str):
        self.mensaje = mensaje
        super().__init__(mensaje)


def _existe_admin() -> bool:
    """¿Existe al menos una cuenta de administrador?

    Patrón de degradación igual al resto de la app (landing, /health y
    context processors): si la BD está caída o aún sin migrar, se devuelve
    True (fail-closed: jamás se habilita el bootstrap administrativo con una
    BD incierta) y la excepción real queda completa y visible en el log.
    """
    try:
        return Usuario.query.filter_by(rol="admin").count() > 0
    except Exception:
        db.session.rollback()
        logger.exception("No se pudo consultar si existe un administrador")
        return True


def _mensaje_duplicado(correo: str, documento: str) -> str:
    """Mensaje amigable tras una violación de unicidad (POST-rollback).

    Nunca lanza: si la re-consulta falla, devuelve el mensaje genérico.
    """
    try:
        if Usuario.query.filter_by(correo=correo).first():
            return "El correo ya está registrado"
        if documento and Cliente.query.filter(Cliente.cedula == documento).first():
            return "Ese documento ya está registrado"
    except Exception:
        db.session.rollback()
    return "No se pudo completar el registro. Intenta nuevamente."


def _cliente_activable(cliente: Cliente) -> bool:
    """True si un Cliente preexistente todavia no es una cuenta en uso.

    El registro publico se enlaza a un Cliente existente solo cuando ese registro
    esta "virgin": sin Usuario asociado y sin historial (vehiculos, citas,
    ordenes, cotizaciones, garantias, asistencias o ubicaciones). Es la unica
    forma de que el flujo "el taller me creo la ficha y la activo yo" siga
    funcionando sin que un tercero pueda adoptar la cuenta de un cliente que ya
    existe: bastaria con conocer su correo.
    """
    if Usuario.query.filter_by(cliente_id=cliente.id).first():
        return False
    from models.asistencia import AsistenciaEmergencia
    from models.cita import Cita
    from models.cotizacion import Cotizacion
    from models.garantia import Garantia
    from models.orden_trabajo import OrdenTrabajo
    from models.ubicacion_cliente import UbicacionCliente
    from models.vehiculo import Vehiculo

    for modelo in (
        Vehiculo,
        Cita,
        OrdenTrabajo,
        Cotizacion,
        Garantia,
        AsistenciaEmergencia,
        UbicacionCliente,
    ):
        if modelo.query.filter_by(cliente_id=cliente.id).first():
            return False
    return True


def _destino_tras_autenticar(usuario) -> str:
    """Endpoint de inicio segun el area del usuario (unica fuente: area_home).

    Un cliente siempre cae en su portal y solo el personal del taller en el area
    administrativa. No volver a decidirlo con comparaciones sueltas de rol.
    """
    return usuario.area_home


def _next_valido(destino: str | None) -> str | None:
    """Destino pedido por el usuario, solo si es una ruta interna segura.

    Evita que `?next=` sea usado para redirigir fuera del sitio (open redirect).
    """
    if not destino or not destino.startswith("/"):
        return None
    if destino.startswith("//") or destino.startswith("/\\"):
        return None
    return destino


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if current_user.is_authenticated:
        return redirect(url_for(current_user.area_home))
    form = LoginForm()
    area = request.args.get("area") or ""
    if area not in ("admin", "cliente"):
        area = ""
    permite_registrar_admin = not _existe_admin()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        password = form.password.data
        usuario: Usuario | None = Usuario.query.filter_by(correo=correo).first()
        if usuario and usuario.check_password(password):
            if not usuario.activo:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "danger")
                return render_template("auth/login.html", form=form, area=area, permite_registrar_admin=permite_registrar_admin)
            login_user(usuario, remember=request.form.get("remember") == "on")
            logger.info("Login exitoso: %s", correo)
            try:
                from datetime import datetime
                usuario.last_access_at = datetime.now()
                safe_commit()
            except Exception as e:
                logger.warning("No se pudo registrar último acceso: %s", e)
            destino = _next_valido(request.args.get("next") or request.form.get("next"))
            return redirect(destino or url_for(_destino_tras_autenticar(usuario)))
        logger.warning("Intento de login fallido: %s", correo)
        flash("Credenciales inválidas", "danger")
    return render_template("auth/login.html", form=form, area=area, permite_registrar_admin=permite_registrar_admin)


@auth_bp.route("/logout")
@login_required
def logout() -> Any:
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register() -> Any:
    if current_user.is_authenticated:
        return redirect(url_for(current_user.area_home))
    form = RegisterForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        documento = form.documento.data.strip()
        try:
            if Usuario.query.filter_by(correo=correo).first():
                raise RegistroError("El correo ya está registrado")
            cliente = Cliente.query.filter(db.func.lower(Cliente.correo) == correo).first()
            por_documento = Cliente.query.filter(Cliente.cedula == documento).first() if documento else None
            # Vincularse a un Cliente preexistente por correo es el flujo de
            # "activar la cuenta que me creo el taller", pero solo es seguro si
            # ese Cliente esta virgin: sin cuenta asociada y sin historial. Si ya
            # es un cliente con vehiculos u ordenes, enlazarse a el permitiria
            # que cualquiera que supiera su correo adoptara su cuenta y viera su
            # informacion. En ese caso el registro se rechaza.
            if cliente is not None and not _cliente_activable(cliente):
                raise RegistroError(
                    "Ese correo ya tiene una ficha de cliente. Inicia sesión con tu cuenta "
                    "o contacta al taller para recuperarla."
                )
            # El documento identifica a un cliente, pero no prueba que quien se
            # registra sea esa persona: nunca sirve por si solo para vincular una
            # cuenta. Solo se acepta cuando pertenece al cliente ya vinculado por
            # correo; en cualquier otro caso el documento está en uso.
            if por_documento is not None and por_documento is not cliente:
                raise RegistroError("Ese documento ya está registrado")
            usuario = Usuario(
                nombre=form.nombre.data.strip(),
                correo=correo,
                rol="cliente",
                cliente_id=cliente.id if cliente else None,
            )
            usuario.set_password(form.password.data)
            if not cliente and correo:
                nuevo_cliente = Cliente(
                    nombre=form.nombre.data.strip(),
                    correo=correo,
                    cedula=documento or None,
                    telefono=(form.telefono.data or "").strip() or None,
                )
                db.session.add(nuevo_cliente)
                db.session.flush()
                usuario.cliente_id = nuevo_cliente.id
            elif cliente and documento:
                if not cliente.cedula:
                    cliente.cedula = documento
                if form.telefono.data and not cliente.telefono:
                    cliente.telefono = form.telefono.data.strip()
            db.session.add(usuario)
            safe_commit()
        except RegistroError as e:
            db.session.rollback()
            logger.warning("Registro rechazado (%s): %s", e.mensaje, correo)
            if request.is_json:
                return json_error(e.mensaje, status=400)
            flash(e.mensaje, "danger")
            return render_template("auth/register.html", form=form)
        except IntegrityError:
            db.session.rollback()
            # Excepción real y visible en el log del servidor (nunca al cliente).
            logger.exception("Registro con conflicto de unicidad: %s", correo)
            if request.is_json:
                return json_error(_mensaje_duplicado(correo, documento), status=400)
            flash(_mensaje_duplicado(correo, documento), "danger")
            return render_template("auth/register.html", form=form)
        except Exception:
            db.session.rollback()
            logger.exception("Error registrando usuario %s", correo)
            mensaje = "No se pudo completar el registro. Intenta nuevamente."
            if request.is_json:
                return json_error(mensaje)
            flash(mensaje, "danger")
            return render_template("auth/register.html", form=form)
        logger.info("Nuevo usuario cliente registrado: %s", correo)
        try:
            from services.notification_service import NotificationService
            NotificationService.notify_staff(
                "sistema",
                "Nuevo cliente registrado",
                f"{form.nombre.data.strip()} creó una cuenta de cliente ({correo}).",
                url_for("clientes.listar"),
            )
        except Exception as ne:
            logger.warning("No se pudo notificar registro de cliente: %s", ne)
        login_user(usuario)
        if request.is_json:
            return jsonify({"success": True, "message": "Registro exitoso."})
        flash("¡Bienvenido/a a SIAM! Tu cuenta fue creada.", "success")
        return redirect(url_for(_destino_tras_autenticar(usuario)))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/registrar-admin", methods=["GET", "POST"])
def registrar_admin() -> Any:
    """Registro de cuenta administrativa del taller.

    Sólo es el bootstrap de la primera instalación: si ya existe una cuenta
    con rol admin, la ruta redirige al login (evita que cualquier visitante
    anónimo cree cuentas de administrador en producción).
    """
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for("portal.index"))
        return redirect(url_for("dashboard.index"))
    if _existe_admin():
        flash("Ya existe una cuenta de administrador. Inicia sesión para gestionar SIAM.", "warning")
        return redirect(url_for("auth.login"))
    form = AdminRegisterForm()
    if form.validate_on_submit():
        correo = form.correo.data.strip().lower()
        if Usuario.query.filter_by(correo=correo).first():
            flash("El correo ya está registrado", "danger")
            return render_template("auth/registrar_admin.html", form=form)
        usuario = Usuario(
            nombre=form.nombre.data.strip(),
            correo=correo,
            rol="admin",
        )
        usuario.set_password(form.password.data)
        db.session.add(usuario)
        try:
            safe_commit()
            logger.info("Nueva cuenta administrativa registrada: %s", correo)
            try:
                from services.notification_service import NotificationService
                NotificationService.notify_staff(
                    "sistema",
                    "Nueva cuenta administrativa",
                    f"Se creó la cuenta administrativa para {correo}.",
                    url_for("configuracion.index"),
                )
            except Exception as ne:
                logger.warning("No se pudo notificar nueva cuenta admin: %s", ne)
            flash("Cuenta administrativa creada. Inicia sesión.", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            db.session.rollback()
            logger.exception("Error registrando administrador %s", correo)
            flash("No se pudo completar el registro. Intenta nuevamente.", "danger")
    return render_template("auth/registrar_admin.html", form=form)
