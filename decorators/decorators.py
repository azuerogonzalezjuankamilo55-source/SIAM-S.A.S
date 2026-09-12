from functools import wraps
from typing import Callable

from flask import flash, redirect, url_for, jsonify, request
from flask_login import current_user

# Roles de personal del taller (no clientes).
STAFF_ROLES: frozenset[str] = frozenset({"admin", "recepcion", "mecanico"})

MENSAJE_LOGIN: str = "Debes iniciar sesión para acceder."
MENSAJE_PERMISO: str = "No tienes permisos de administrador."


def roles_required(*roles: str):
    """Restringe una vista a uno o varios roles concretos.

    Usuarios no autenticados conservan el flujo de login; usuarios autenticados
    sin permiso reciben 403 (JSON para peticiones AJAX/API).
    """
    allowed = frozenset(roles)
    if not allowed:
        raise ValueError("roles_required requiere al menos un rol")

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.accept_mimetypes.best == "application/json":
                    return jsonify(success=False, error=MENSAJE_LOGIN), 401
                flash(MENSAJE_LOGIN, "warning")
                return redirect(url_for("auth.login"))
            if current_user.rol not in allowed:
                if request.is_json or request.accept_mimetypes.best == "application/json":
                    return jsonify(success=False, error=MENSAJE_PERMISO), 403
                flash(MENSAJE_PERMISO, "danger")
                target = "portal.index" if current_user.rol == "cliente" else "dashboard.index"
                return redirect(url_for(target))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f: Callable) -> Callable:
    """Decorator that restricts access to admin users only."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(MENSAJE_LOGIN, "warning")
            return redirect(url_for("auth.login"))
        if current_user.rol != "admin":
            flash(MENSAJE_PERMISO, "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)

    return decorated_function


def staff_required(f: Callable) -> Callable:
    """Decorator that restricts access to workshop staff (no clientes)."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(MENSAJE_LOGIN, "warning")
            return redirect(url_for("auth.login"))
        if current_user.rol not in STAFF_ROLES:
            flash(MENSAJE_PERMISO, "danger")
            return redirect(url_for("portal.index"))
        return f(*args, **kwargs)

    return decorated_function


def staff_blueprint_guard() -> None:
    """Guarda de blueprint: solo personal del taller (no clientes).

    Se registra como before_request en los módulos administrativos.
    Usuarios no autenticados van al login; un usuario con rol "cliente"
    (o desconocido) es redirigido a su portal.
    """
    if not current_user.is_authenticated:
        flash(MENSAJE_LOGIN, "warning")
        return redirect(url_for("auth.login"))
    if current_user.rol in STAFF_ROLES:
        return None
    flash(MENSAJE_PERMISO, "danger")
    return redirect(url_for("portal.index"))
