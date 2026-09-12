from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cliente import Cliente
    from models.cita import Cita


class UbicacionCliente(db.Model):
    """Ubicación compartida en vivo de un cliente con una cita activa."""

    __tablename__ = "ubicaciones_cliente"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    cliente_id: int = db.Column(
        db.Integer, db.ForeignKey("clientes.id"), nullable=False, index=True
    )
    cita_id: int | None = db.Column(
        db.Integer, db.ForeignKey("citas.id"), nullable=True, index=True
    )
    latitude: float = db.Column(db.Float, nullable=False)
    longitude: float = db.Column(db.Float, nullable=False)
    accuracy: float | None = db.Column(db.Float, nullable=True)
    sharing_active: bool = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.true()
    )
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    cliente: "Cliente" = db.relationship(
        "Cliente", backref=db.backref("ubicaciones", lazy="select"), lazy="joined"
    )
    cita: "Cita | None" = db.relationship(
        "Cita",
        backref=db.backref("ubicaciones", lazy="select", cascade="all, delete-orphan"),
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<UbicacionCliente {self.id}:cliente={self.cliente_id} "
            f"cita={self.cita_id} activa={self.sharing_active}>"
        )