from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cita import Cita


class Vehiculo(db.Model):
    __tablename__ = "vehiculos"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    cliente_id: int = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    marca: str = db.Column(db.String(50), nullable=False)
    modelo: str = db.Column(db.String(50), nullable=False)
    anio: int | None = db.Column(db.Integer)
    placa: str = db.Column(db.String(20), unique=True, nullable=False)
    vin: str | None = db.Column(db.String(17), unique=True)
    color: str | None = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    citas: list["Cita"] = db.relationship(
        "Cita", backref="vehiculo", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Vehiculo {self.id}:{self.placa} {self.marca} {self.modelo}>"
