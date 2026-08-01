from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.categoria_inventario import CategoriaInventario
    from models.movimiento_inventario import MovimientoInventario


class Inventario(db.Model):
    __tablename__ = "inventario"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(150), nullable=False)
    descripcion: str | None = db.Column(db.Text)
    sku: str | None = db.Column(db.String(50), unique=True, nullable=True)
    codigo_barras: str | None = db.Column(db.String(100), nullable=True)
    ubicacion: str | None = db.Column(db.String(50), nullable=True)
    cantidad: int = db.Column(db.Integer, nullable=False, default=0)
    precio_compra: Decimal | None = db.Column(db.Numeric(10, 2))
    precio_venta: Decimal | None = db.Column(db.Numeric(10, 2))
    costo_promedio: Decimal | None = db.Column(db.Numeric(10, 2))
    proveedor: str | None = db.Column(db.String(100))
    categoria_id: int | None = db.Column(db.Integer, db.ForeignKey("categorias_inventario.id"), nullable=True)
    stock_minimo: int = db.Column(db.Integer, default=0)
    stock_critico: int = db.Column(db.Integer, default=0)
    activo: bool = db.Column(db.Boolean, default=True)
    motivo_baja: str | None = db.Column(db.Text)
    fecha_baja = db.Column(db.DateTime)
    usuario_baja_id: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    usuario_baja = db.relationship(
        "Usuario", backref="bajas_inventario", foreign_keys=[usuario_baja_id], lazy="joined"
    )

    movimientos: list["MovimientoInventario"] = db.relationship(
        "MovimientoInventario", backref="item", lazy="select", order_by="MovimientoInventario.created_at.desc()"
    )

    @property
    def es_baja(self) -> bool:
        return self.fecha_baja is not None

    @property
    def stock_bajo(self) -> bool:
        return not self.es_baja and self.cantidad <= self.stock_minimo

    @property
    def stock_critico_alcanzado(self) -> bool:
        return not self.es_baja and self.cantidad <= self.stock_critico

    @property
    def categoria_nombre(self) -> str | None:
        return self.categoria_obj.nombre if self.categoria_obj else None

    @property
    def ganancia_estimada(self) -> Decimal | None:
        if self.precio_venta and self.precio_compra:
            return self.precio_venta - self.precio_compra
        return None

    def registrar_movimiento(
        self, tipo: str, cantidad: int, usuario_id: int, motivo: str | None = None, referencia: str | None = None
    ) -> "MovimientoInventario":
        from models.movimiento_inventario import MovimientoInventario

        saldo_anterior = self.cantidad
        if tipo == "entrada":
            self.cantidad += cantidad
        elif tipo == "salida":
            self.cantidad = max(0, self.cantidad - cantidad)
        elif tipo in ("ajuste", "baja"):
            self.cantidad = 0 if tipo == "baja" else max(0, cantidad)

        movimiento = MovimientoInventario(
            inventario_id=self.id,
            tipo=tipo,
            cantidad=cantidad,
            saldo_anterior=saldo_anterior,
            saldo_posterior=self.cantidad,
            motivo=motivo,
            referencia=referencia,
            usuario_id=usuario_id,
        )
        db.session.add(movimiento)
        return movimiento

    def __repr__(self) -> str:
        return f"<Inventario {self.id}:{self.nombre} stock={self.cantidad}>"
