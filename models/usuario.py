from typing import TYPE_CHECKING

from database.db import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

if TYPE_CHECKING:
    from models.cliente import Cliente


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    __allow_unmapped__ = True

    #: Roles que pertenecen al personal del taller (no son clientes).
    ROLES_STAFF: frozenset[str] = frozenset({"admin", "recepcion", "mecanico"})

    #: Etiquetas legibles para identificar al usuario (fase 26.3).
    ROL_LABELS: dict[str, str] = {
        "admin": "Administrador",
        "recepcion": "Personal de taller",
        "mecanico": "Personal de taller",
        "cliente": "Cliente",
    }

    #: Contexto de area para la interfaz (fase 26.2).
    AREA_ADMINISTRATIVA: str = "administrativa"
    AREA_PORTAL_CLIENTE: str = "portal_cliente"

    AREA_LABELS: dict[str, str] = {
        AREA_ADMINISTRATIVA: "Área Administrativa",
        AREA_PORTAL_CLIENTE: "Portal del Cliente",
    }

    AREA_ICONS: dict[str, str] = {
        AREA_ADMINISTRATIVA: "fa-screwdriver-wrench",
        AREA_PORTAL_CLIENTE: "fa-id-badge",
    }

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(100), nullable=False)
    correo: str = db.Column(db.String(120), unique=True, nullable=False)
    password_hash: str = db.Column(db.String(255), nullable=False)
    rol: str = db.Column(db.String(20), nullable=False, default="cliente")
    activo: bool = db.Column(db.Boolean, default=True)
    foto_path: str | None = db.Column(db.String(300))
    cliente_id: int | None = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    last_access_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    cliente: "Cliente | None" = db.relationship(
        "Cliente",
        backref=db.backref("usuario", uselist=False, lazy="joined"),
        uselist=False,
        lazy="joined",
    )

    @property
    def es_cliente(self) -> bool:
        return self.rol == "cliente"

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"

    @property
    def es_staff(self) -> bool:
        """True si el usuario pertenece al area administrativa del taller."""
        return self.rol in self.ROLES_STAFF

    @property
    def rol_label(self) -> str:
        """Nombre legible del rol: Administrador / Personal de taller / Cliente."""
        return self.ROL_LABELS.get(self.rol, self.rol.replace("_", " ").capitalize())

    @property
    def area(self) -> str:
        return self.AREA_ADMINISTRATIVA if self.es_staff else self.AREA_PORTAL_CLIENTE

    @property
    def area_label(self) -> str:
        return self.AREA_LABELS.get(self.area, "SIAM")

    @property
    def area_icon(self) -> str:
        return self.AREA_ICONS.get(self.area, "fa-gears")

    @property
    def area_home(self) -> str:
        """Endpoint de inicio del area del usuario."""
        return "dashboard.index" if self.es_staff else "portal.index"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<Usuario {self.id}:{self.correo} rol={self.rol}>"
