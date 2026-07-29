from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.vehiculo import Vehiculo
    from models.cita import Cita


class Cliente(db.Model):
    __tablename__ = "clientes"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(150), nullable=False)
    telefono: str | None = db.Column(db.String(20))
    correo: str | None = db.Column(db.String(120))
    direccion: str | None = db.Column(db.Text)
    cedula: str | None = db.Column(db.String(20), unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    vehiculos: list["Vehiculo"] = db.relationship(
        "Vehiculo", backref="cliente", lazy="select", cascade="all, delete-orphan"
    )
    citas: list["Cita"] = db.relationship(
        "Cita", backref="cliente", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cliente {self.id}:{self.nombre}>"
