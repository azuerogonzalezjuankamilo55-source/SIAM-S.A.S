from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.orden_trabajo import OrdenTrabajo
    from models.inventario import Inventario


class OrdenTrabajoRepuesto(db.Model):
    __tablename__ = "ordenes_trabajo_repuestos"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    orden_trabajo_id: int = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=False)
    inventario_id: int = db.Column(db.Integer, db.ForeignKey("inventario.id"), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    nota: str | None = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    inventario: "Inventario" = db.relationship("Inventario", lazy="joined")

    @property
    def subtotal(self) -> Decimal:
        return (self.precio_unitario * self.cantidad).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return f"<OTRepuesto {self.id}:{self.inventario_id} x{self.cantidad}>"
