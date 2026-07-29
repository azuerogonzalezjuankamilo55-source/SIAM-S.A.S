from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.inventario import Inventario
    from models.usuario import Usuario

TIPOS_MOVIMIENTO = ["entrada", "salida", "ajuste"]


class MovimientoInventario(db.Model):
    __tablename__ = "movimientos_inventario"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    inventario_id: int = db.Column(db.Integer, db.ForeignKey("inventario.id"), nullable=False)
    tipo: str = db.Column(db.String(20), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False)
    saldo_anterior: int = db.Column(db.Integer, nullable=False)
    saldo_posterior: int = db.Column(db.Integer, nullable=False)
    motivo: str | None = db.Column(db.Text)
    referencia: str | None = db.Column(db.String(100))
    usuario_id: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def tipo_display(self) -> str:
        labels = {"entrada": "Entrada", "salida": "Salida", "ajuste": "Ajuste"}
        return labels.get(self.tipo, self.tipo)

    @property
    def tipo_clase(self) -> str:
        clases = {"entrada": "success", "salida": "danger", "ajuste": "warning"}
        return clases.get(self.tipo, "secondary")

    def __repr__(self) -> str:
        return f"<MovimientoInventario {self.id}:{self.tipo} qty={self.cantidad}>"
