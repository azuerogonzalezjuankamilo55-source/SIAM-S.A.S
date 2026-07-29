from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.usuario import Usuario


class PagoFactura(db.Model):
    __tablename__ = "pagos_factura"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    factura_id: int = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=False)
    monto: Decimal = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago: str = db.Column(db.String(30), nullable=False)
    referencia: str | None = db.Column(db.String(100))
    estado: str = db.Column(db.String(20), nullable=False, default="confirmado")
    usuario_id: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    notas: str | None = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def metodo_pago_display(self) -> str:
        labels = {
            "Efectivo": "Efectivo",
            "Tarjeta Débito": "Tarjeta Débito",
            "Tarjeta Crédito": "Tarjeta Crédito",
            "Transferencia": "Transferencia",
            "PSE": "PSE",
            "Nequi": "Nequi",
            "Daviplata": "Daviplata",
        }
        return labels.get(self.metodo_pago, self.metodo_pago)

    def __repr__(self) -> str:
        return f"<PagoFactura {self.id}:factura={self.factura_id} monto={self.monto}>"
