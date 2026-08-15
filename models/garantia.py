from datetime import date, timedelta
from typing import TYPE_CHECKING

from database.db import db


ESTADOS_GARANTIA = ["activa", "caducada", "reclamada", "anulada"]

ESTADOS_GARANTIA_LABELS = {
    "activa": "Activa",
    "caducada": "Caducada",
    "reclamada": "Reclamada",
    "anulada": "Anulada",
}


class Garantia(db.Model):
    __tablename__ = "garantias"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    codigo: str = db.Column(db.String(20), unique=True, nullable=False)
    cliente_id: int = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    vehiculo_id: int = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=False)
    orden_trabajo_id: int | None = db.Column(
        db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=True
    )
    factura_id: int | None = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=True)
    servicio_id: int | None = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=True)
    descripcion: str = db.Column(db.String(500), nullable=False)
    meses_validez: int = db.Column(db.Integer, nullable=False, default=3)
    fecha_inicio: db.Date = db.Column(db.Date, nullable=False, default=date.today)
    fecha_fin: db.Date = db.Column(db.Date, nullable=False)
    estado: str = db.Column(db.String(20), nullable=False, default="activa")
    nota_reclamacion: str | None = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    cliente = db.relationship("Cliente", backref="garantias", lazy="joined")
    vehiculo = db.relationship("Vehiculo", backref="garantias", lazy="joined")
    orden_trabajo = db.relationship("OrdenTrabajo", backref="garantias", lazy="joined")
    factura = db.relationship("Factura", backref="garantias", lazy="joined")
    servicio = db.relationship("Servicio", backref="garantias", lazy="joined")

    @property
    def estado_display(self) -> str:
        return ESTADOS_GARANTIA_LABELS.get(self.estado, self.estado)

    @property
    def dias_restantes(self) -> int:
        return (self.fecha_fin - date.today()).days

    @property
    def vigente(self) -> bool:
        return self.estado == "activa" and self.dias_restantes >= 0

    def __repr__(self) -> str:
        return f"<Garantia {self.codigo}:{self.estado}>"
