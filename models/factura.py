from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.servicio import Servicio
    from models.pago_factura import PagoFactura
    from models.orden_trabajo import OrdenTrabajo

METODOS_PAGO = [
    ("Efectivo", "Efectivo"),
    ("Tarjeta Débito", "Tarjeta Débito"),
    ("Tarjeta Crédito", "Tarjeta Crédito"),
    ("Transferencia", "Transferencia"),
    ("PSE", "PSE"),
    ("Nequi", "Nequi"),
    ("Daviplata", "Daviplata"),
]

ESTADOS_FACTURA = ["pendiente", "parcial", "pagado", "anulado"]

COLORES_ESTADO_FACTURA = {
    "pendiente": "warning",
    "parcial": "info",
    "pagado": "success",
    "anulado": "danger",
}


class Factura(db.Model):
    __tablename__ = "facturas"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    cita_id: int = db.Column(db.Integer, db.ForeignKey("citas.id"), nullable=False)
    orden_trabajo_id: int | None = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=True)
    numero: str = db.Column(db.String(20), unique=True, nullable=False)
    subtotal: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    iva_porcentaje: Decimal = db.Column(db.Numeric(4, 2), nullable=False, default=Decimal("19.00"))
    iva: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    descuento: Decimal = db.Column(db.Numeric(10, 2), default=0)
    total: Decimal = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago: str | None = db.Column(db.String(30))
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente")
    notas: str | None = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    orden_trabajo: "OrdenTrabajo | None" = db.relationship("OrdenTrabajo", backref="facturas", lazy="joined")

    detalles: list["FacturaDetalle"] = db.relationship(
        "FacturaDetalle", backref="factura", lazy="select", cascade="all, delete-orphan"
    )
    pagos: list["PagoFactura"] = db.relationship(
        "PagoFactura", backref="factura", lazy="select", cascade="all, delete-orphan",
        order_by="PagoFactura.created_at.desc()",
    )

    @property
    def monto_pagado(self) -> Decimal:
        return sum((p.monto for p in self.pagos if p.estado == "confirmado"), Decimal("0"))

    @property
    def saldo_pendiente(self) -> Decimal:
        return self.total - self.monto_pagado

    @property
    def estado_actualizado(self) -> str:
        if self.estado == "anulado":
            return "anulado"
        pagado = self.monto_pagado
        if pagado >= self.total:
            return "pagado"
        if pagado > 0:
            return "parcial"
        return self.estado

    @property
    def estado_color(self) -> str:
        return COLORES_ESTADO_FACTURA.get(self.estado_actualizado, "secondary")

    def __repr__(self) -> str:
        return f"<Factura {self.id}:{self.numero} total={self.total}>"


class FacturaDetalle(db.Model):
    __tablename__ = "facturas_detalle"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    factura_id: int = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=False)
    servicio_id: int = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario: Decimal = db.Column(db.Numeric(10, 2), nullable=False)
    descuento: Decimal = db.Column(db.Numeric(10, 2), default=0)
    subtotal: Decimal = db.Column(db.Numeric(10, 2), nullable=False)

    def __repr__(self) -> str:
        return f"<FacturaDetalle {self.id}:servicio={self.servicio_id} cant={self.cantidad}>"
