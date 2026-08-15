from decimal import Decimal

from database.db import db


class CotizacionItem(db.Model):
    __tablename__ = "cotizaciones_items"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    cotizacion_id: int = db.Column(db.Integer, db.ForeignKey("cotizaciones.id"), nullable=False)
    servicio_id: int | None = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=True)
    descripcion: str = db.Column(db.String(300), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    subtotal: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    @property
    def es_servicio(self) -> bool:
        return self.servicio_id is not None

    def __repr__(self) -> str:
        return f"<CotizacionItem {self.id}:{self.descripcion}>"
