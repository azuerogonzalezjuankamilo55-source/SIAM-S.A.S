from functools import wraps
from typing import Callable

from flask import flash, redirect, url_for
from flask_login import current_user

# Roles de personal del taller (no clientes).
STAFF_ROLES: frozenset[str] = frozenset({"admin", "recepcion", "mecanico"})

MENSAJE_LOGIN: str = "Debes iniciar sesión para acceder."
MENSAJE_PERMISO: str = "No tienes permisos de administrador."


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
