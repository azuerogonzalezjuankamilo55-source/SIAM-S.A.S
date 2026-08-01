from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.factura import FacturaDetalle


class Servicio(db.Model):
    __tablename__ = "servicios"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(100), nullable=False)
    descripcion: str | None = db.Column(db.Text)
    precio_estimado: Decimal | None = db.Column(db.Numeric(10, 2))
    duracion_estimada: int | None = db.Column(db.Integer, comment="Minutos")
    categoria: str | None = db.Column(db.String(50))
    imagen_path: str | None = db.Column(db.String(300))
    activo: bool = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    detalles: list["FacturaDetalle"] = db.relationship(
        "FacturaDetalle", backref="servicio", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Servicio {self.id}:{self.nombre}>"
