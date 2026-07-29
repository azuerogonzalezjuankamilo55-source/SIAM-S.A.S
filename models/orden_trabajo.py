from datetime import date
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cliente import Cliente
    from models.vehiculo import Vehiculo
    from models.mecanico import Mecanico
    from models.orden_trabajo_historial import OrdenTrabajoHistorial


ESTADOS_OT = [
    "recibido",
    "diagnostico",
    "esperando_repuestos",
    "en_reparacion",
    "listo_entrega",
    "entregado",
]


class OrdenTrabajo(db.Model):
    __tablename__ = "ordenes_trabajo"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    numero: str = db.Column(db.String(20), unique=True, nullable=False)
    cliente_id: int = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    vehiculo_id: int = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=False)
    mecanico_id: int | None = db.Column(db.Integer, db.ForeignKey("mecanicos.id"), nullable=True)
    fecha_ingreso = db.Column(db.Date, nullable=False, default=date.today)
    fecha_estimada_entrega = db.Column(db.Date, nullable=True)
    diagnostico_inicial: str | None = db.Column(db.Text)
    observaciones: str | None = db.Column(db.Text)
    estado: str = db.Column(db.String(30), nullable=False, default="recibido")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    cliente: "Cliente" = db.relationship("Cliente", backref="ordenes_trabajo", lazy="joined")
    vehiculo: "Vehiculo" = db.relationship("Vehiculo", backref="ordenes_trabajo", lazy="joined")
    mecanico: "Mecanico | None" = db.relationship("Mecanico", backref="ordenes_trabajo", lazy="joined")

    historial: list["OrdenTrabajoHistorial"] = db.relationship(
        "OrdenTrabajoHistorial", backref="orden", lazy="select",
        cascade="all, delete-orphan", order_by="OrdenTrabajoHistorial.created_at.desc()"
    )

    @property
    def estado_display(self) -> str:
        labels = {
            "recibido": "Recibido",
            "diagnostico": "Diagnóstico",
            "esperando_repuestos": "Esperando Repuestos",
            "en_reparacion": "En Reparación",
            "listo_entrega": "Listo para Entrega",
            "entregado": "Entregado",
        }
        return labels.get(self.estado, self.estado)

    def __repr__(self) -> str:
        return f"<OrdenTrabajo {self.numero}:{self.estado}>"
