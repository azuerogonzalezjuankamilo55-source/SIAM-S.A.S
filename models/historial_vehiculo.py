from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.vehiculo import Vehiculo
    from models.cita import Cita
    from models.factura import Factura
    from models.orden_trabajo import OrdenTrabajo
    from models.usuario import Usuario
    from models.historial_foto import HistorialFoto

TIPOS_HISTORIAL = [
    "cita",
    "reparacion",
    "mantenimiento",
    "cambio_aceite",
    "cambio_frenos",
    "alineacion",
    "balanceo",
    "llantas",
    "bateria",
    "revision",
    "factura",
    "fotografia",
    "observacion",
    "diagnostico",
]

TIPOS_HISTORIAL_LABELS = {
    "cita": "Cita",
    "reparacion": "Reparación",
    "mantenimiento": "Mantenimiento",
    "cambio_aceite": "Cambio de aceite",
    "cambio_frenos": "Cambio de frenos",
    "alineacion": "Alineación",
    "balanceo": "Balanceo",
    "llantas": "Neumáticos",
    "bateria": "Batería",
    "revision": "Revisión",
    "factura": "Factura",
    "fotografia": "Fotografía",
    "observacion": "Observación",
    "diagnostico": "Diagnóstico",
}


class HistorialVehiculo(db.Model):
    __tablename__ = "historial_vehiculo"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    vehiculo_id: int = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=False)
    tipo: str = db.Column(db.String(30), nullable=False)
    descripcion: str | None = db.Column(db.Text)
    fecha = db.Column(db.Date, nullable=False)
    kilometraje: int | None = db.Column(db.Integer)
    foto_path: str | None = db.Column(db.String(300))
    cita_id: int | None = db.Column(db.Integer, db.ForeignKey("citas.id"), nullable=True)
    factura_id: int | None = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=True)
    orden_trabajo_id: int | None = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=True)
    creado_por: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    vehiculo: "Vehiculo" = db.relationship("Vehiculo", backref="historial", lazy="joined")
    cita: "Cita | None" = db.relationship("Cita", backref="historial_vehicular", lazy="joined")
    factura: "Factura | None" = db.relationship("Factura", backref="historial_vehicular", lazy="joined")
    orden: "OrdenTrabajo | None" = db.relationship("OrdenTrabajo", backref="historial_vehicular", lazy="joined")
    fotos: list["HistorialFoto"] = db.relationship(
        "HistorialFoto", lazy="select", cascade="all, delete-orphan",
        order_by="HistorialFoto.id",
    )

    def fotos_por_tipo(self, tipo: str) -> list["HistorialFoto"]:
        return [f for f in self.fotos if f.tipo == tipo]

    @property
    def tipo_label(self) -> str:
        return TIPOS_HISTORIAL_LABELS.get(self.tipo, self.tipo)

    def __repr__(self) -> str:
        return f"<HistorialVehiculo {self.id}:{self.tipo} vehiculo={self.vehiculo_id}>"
