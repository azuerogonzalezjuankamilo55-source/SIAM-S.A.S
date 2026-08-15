from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cotizacion_item import CotizacionItem


ESTADOS_COTIZACION = ["pendiente", "aprobada", "rechazada", "convertida", "vencida"]

ESTADOS_COTIZACION_LABELS = {
    "pendiente": "Pendiente",
    "aprobada": "Aprobada",
    "rechazada": "Rechazada",
    "convertida": "Convertida en OT",
    "vencida": "Vencida",
}


class Cotizacion(db.Model):
    __tablename__ = "cotizaciones"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    numero: str = db.Column(db.String(20), unique=True, nullable=False)
    cliente_id: int = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    vehiculo_id: int = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=False)
    sede_id: int | None = db.Column(db.Integer, db.ForeignKey("sedes.id"), nullable=True)
    orden_trabajo_id: int | None = db.Column(
        db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=True
    )
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente")
    descripcion: str | None = db.Column(db.Text)
    validez_dias: int = db.Column(db.Integer, nullable=False, default=15)
    subtotal: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    iva_porcentaje: Decimal = db.Column(db.Numeric(4, 2), nullable=False, default=Decimal("19.00"))
    iva: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    descuento: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    items: list["CotizacionItem"] = db.relationship(
        "CotizacionItem", backref="cotizacion", lazy="select",
        cascade="all, delete-orphan",
    )
    cliente = db.relationship("Cliente", backref="cotizaciones", lazy="joined")
    vehiculo = db.relationship("Vehiculo", backref="cotizaciones", lazy="joined")
    sede = db.relationship("Sede", backref="cotizaciones", lazy="joined")
    orden_trabajo = db.relationship("OrdenTrabajo", backref="cotizaciones", lazy="joined")

    @property
    def estado_display(self) -> str:
        return ESTADOS_COTIZACION_LABELS.get(self.estado, self.estado)

    def __repr__(self) -> str:
        return f"<Cotizacion {self.numero}:{self.estado}>"
