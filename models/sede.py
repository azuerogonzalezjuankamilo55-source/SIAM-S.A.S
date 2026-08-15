from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cita import Cita


class Sede(db.Model):
    __tablename__ = "sedes"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(150), nullable=False)
    direccion: str | None = db.Column(db.String(300))
    telefono: str | None = db.Column(db.String(30))
    horario: str | None = db.Column(db.String(250))
    latitud: float | None = db.Column(db.Float)
    longitud: float | None = db.Column(db.Float)
    servicios: str | None = db.Column(db.Text, comment="Lista de servicios en JSON")
    activo: bool = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    citas: list["Cita"] = db.relationship(
        "Cita", backref="sede", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Sede {self.id}:{self.nombre}>"
