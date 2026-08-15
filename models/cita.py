from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.factura import Factura


class Cita(db.Model):
    __tablename__ = "citas"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    cliente_id: int = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    vehiculo_id: int = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=False)
    mecanico_id: int | None = db.Column(db.Integer, db.ForeignKey("mecanicos.id"), nullable=True)
    sede_id: int | None = db.Column(db.Integer, db.ForeignKey("sedes.id"), nullable=True)
    servicio_id: int | None = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=True)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente")
    descripcion: str | None = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    factura: "Factura | None" = db.relationship(
        "Factura", backref="cita", uselist=False, lazy="joined", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cita {self.id}:{self.fecha} {self.hora} estado={self.estado}>"
