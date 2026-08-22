from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cliente import Cliente
    from models.vehiculo import Vehiculo
    from models.mecanico import Mecanico
    from models.orden_trabajo_historial import OrdenTrabajoHistorial
    from models.orden_trabajo_item import OrdenTrabajoItem
    from models.orden_trabajo_foto import OrdenTrabajoFoto
    from models.orden_trabajo_repuesto import OrdenTrabajoRepuesto


ESTADOS_OT = [
    "recibido",
    "diagnostico",
    "esperando_repuestos",
    "en_reparacion",
    "pruebas",
    "listo_entrega",
    "entregado",
]

ESTADOS_OT_LABELS = {
    "recibido": "Recibido",
    "diagnostico": "Diagnóstico",
    "esperando_repuestos": "Esperando Repuestos",
    "en_reparacion": "En Reparación",
    "pruebas": "En Pruebas",
    "listo_entrega": "Listo para Entrega",
    "entregado": "Entregado",
}

ESTADOS_OT_CHOICES = [(estado, ESTADOS_OT_LABELS[estado]) for estado in ESTADOS_OT]


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
    kms_ingreso: int | None = db.Column(db.Integer)
    nivel_combustible_ingreso: str | None = db.Column(db.String(20))
    kms_salida: int | None = db.Column(db.Integer)
    nivel_combustible_salida: str | None = db.Column(db.String(20))
    fecha_entrega = db.Column(db.Date, nullable=True)
    firma_mecanico_path: str | None = db.Column(db.String(300))
    firma_cliente_path: str | None = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    cliente: "Cliente" = db.relationship("Cliente", backref="ordenes_trabajo", lazy="joined")
    vehiculo: "Vehiculo" = db.relationship("Vehiculo", backref="ordenes_trabajo", lazy="joined")
    mecanico: "Mecanico | None" = db.relationship("Mecanico", backref="ordenes_trabajo", lazy="joined")

    historial: list["OrdenTrabajoHistorial"] = db.relationship(
        "OrdenTrabajoHistorial", backref="orden", lazy="select",
        cascade="all, delete-orphan", order_by="OrdenTrabajoHistorial.created_at.desc()"
    )

    items: list["OrdenTrabajoItem"] = db.relationship(
        "OrdenTrabajoItem", lazy="select",
        cascade="all, delete-orphan", order_by="OrdenTrabajoItem.posicion"
    )
    fotos: list["OrdenTrabajoFoto"] = db.relationship(
        "OrdenTrabajoFoto", lazy="select",
        cascade="all, delete-orphan", order_by="OrdenTrabajoFoto.created_at.desc()"
    )
    repuestos: list["OrdenTrabajoRepuesto"] = db.relationship(
        "OrdenTrabajoRepuesto", lazy="select",
        cascade="all, delete-orphan"
    )

    @property
    def estado_display(self) -> str:
        labels = {
            "recibido": "Recibido",
            "diagnostico": "Diagnóstico",
            "esperando_repuestos": "Esperando Repuestos",
            "en_reparacion": "En Reparación",
            "pruebas": "En Pruebas",
            "listo_entrega": "Listo para Entrega",
            "entregado": "Entregado",
        }
        return labels.get(self.estado, self.estado)

    @property
    def items_completados(self) -> int:
        return sum(1 for i in self.items if i.completado)

    @property
    def tiempo_total_minutos(self) -> int:
        return sum((i.tiempo_minutos or 0) for i in self.items)

    @property
    def total_repuestos(self) -> Decimal:
        return sum((r.subtotal for r in self.repuestos), Decimal("0")).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return f"<OrdenTrabajo {self.numero}:{self.estado}>"
