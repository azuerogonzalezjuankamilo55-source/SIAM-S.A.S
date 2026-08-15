from typing import TYPE_CHECKING

from database.db import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

if TYPE_CHECKING:
    from models.cliente import Cliente


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    __allow_unmapped__ = True

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

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<Usuario {self.id}:{self.correo} rol={self.rol}>"
