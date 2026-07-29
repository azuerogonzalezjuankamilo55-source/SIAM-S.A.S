from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cita import Cita


class Mecanico(db.Model):
    __tablename__ = "mecanicos"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(100), nullable=False)
    telefono: str | None = db.Column(db.String(20))
    correo: str | None = db.Column(db.String(120))
    especialidad: str | None = db.Column(db.String(100))
    activo: bool = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    citas: list["Cita"] = db.relationship(
        "Cita", backref="mecanico", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Mecanico {self.id}:{self.nombre}>"
