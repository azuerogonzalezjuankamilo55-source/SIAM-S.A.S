from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.vehiculo import Vehiculo

TIPOS_RECORDATORIO = ["mantenimiento", "cita", "factura_pendiente", "manual", "reposicion"]
ESTADOS_RECORDATORIO = ["pendiente", "enviado", "completado", "cancelado"]
CANALES_RECORDATORIO = ["portal", "correo", "whatsapp"]

TIPOS_MANTENIMIENTO = [
    "aceite",
    "frenos",
    "balanceo",
    "alineacion",
    "llantas",
    "bateria",
]

TIPOS_MANTENIMIENTO_LABELS = {
    "aceite": "Cambio de aceite y filtro",
    "frenos": "Revisión de frenos",
    "balanceo": "Balanceo de llantas",
    "alineacion": "Alineación",
    "llantas": "Rotación de neumáticos",
    "bateria": "Prueba de batería",
}

ESTADOS_RECORDATORIO_LABELS = {
    "pendiente": "Pendiente",
    "enviado": "Enviado",
    "completado": "Completado",
    "cancelado": "Cancelado",
}


class Recordatorio(db.Model):
    __tablename__ = "recordatorios"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    vehiculo_id: int | None = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=True, index=True)
    tipo: str = db.Column(db.String(30), nullable=False, default="mantenimiento")
    servicio_mantenimiento: str | None = db.Column(db.String(30))
    titulo: str = db.Column(db.String(200), nullable=False)
    descripcion: str | None = db.Column(db.Text)
    fecha_programada = db.Column(db.Date, nullable=False)
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente", index=True)
    canal: str = db.Column(db.String(20), nullable=False, default="portal")
    enviado_at = db.Column(db.DateTime)
    completado_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    vehiculo: "Vehiculo" = db.relationship("Vehiculo", backref="recordatorios", lazy="joined")

    @property
    def estado_label(self) -> str:
        return ESTADOS_RECORDATORIO_LABELS.get(self.estado, self.estado)

    @property
    def tipo_label(self) -> str:
        if self.tipo == "mantenimiento":
            return TIPOS_MANTENIMIENTO_LABELS.get(self.servicio_mantenimiento or "", "Mantenimiento")
        if self.tipo == "reposicion":
            return "Reposición de stock"
        return self.tipo.replace("_", " ").capitalize()

    def __repr__(self) -> str:
        return f"<Recordatorio {self.id}:{self.titulo} vehiculo={self.vehiculo_id} estado={self.estado}>"
