from functools import wraps
from typing import Callable

from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(f: Callable) -> Callable:
    """Decorator that restricts access to admin users only."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Debes iniciar sesión para acceder.", "warning")
            return redirect(url_for("auth.login"))
        if current_user.rol != "admin":
            flash("No tienes permisos de administrador.", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)

    return decorated_function
