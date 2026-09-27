from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cliente import Cliente
    from models.vehiculo import Vehiculo


class AsistenciaEmergencia(db.Model):
    __tablename__ = "asistencias_emergencia"
    __allow_unmapped__ = True

    ESTADOS = ("pendiente", "en_camino", "atendido", "cancelado")
    ESTADOS_LABELS = {
        "pendiente": "Pendiente",
        "en_camino": "En camino",
        "atendido": "Atendido",
        "cancelado": "Cancelado",
    }

    id: int = db.Column(db.Integer, primary_key=True)
    usuario_id: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    cliente_id: int | None = db.Column(
        db.Integer, db.ForeignKey("clientes.id"), nullable=True, index=True
    )
    vehiculo_id: int | None = db.Column(
        db.Integer, db.ForeignKey("vehiculos.id"), nullable=True, index=True
    )
    cliente_nombre: str | None = db.Column(db.String(150))
    telefono: str | None = db.Column(db.String(20))
    descripcion: str | None = db.Column(db.Text)
    latitud: float | None = db.Column(db.Float)
    longitud: float | None = db.Column(db.Float)
    precision_metros: float | None = db.Column(db.Float)
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    cliente: "Cliente | None" = db.relationship(
        "Cliente", backref=db.backref("asistencias", lazy="select"), lazy="joined"
    )
    vehiculo: "Vehiculo | None" = db.relationship(
        "Vehiculo", backref=db.backref("asistencias", lazy="select"), lazy="joined"
    )

    @property
    def estado_label(self) -> str:
        return self.ESTADOS_LABELS.get(self.estado, self.estado.capitalize())

    @property
    def solicitante(self) -> str:
        """Nombre del cliente que pidió la asistencia (texto guardado o relación)."""
        if self.cliente_nombre:
            return self.cliente_nombre
        if self.cliente:
            return self.cliente.nombre
        return "Sin identificar"

    @property
    def vehiculo_label(self) -> str:
        """Descriptor del vehículo con datos reales; vacío si no se asocia uno."""
        if not self.vehiculo:
            return ""
        from services.vehiculo_service import VehiculoService

        return VehiculoService.descriptor(self.vehiculo)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "descripcion": self.descripcion,
            "estado": self.estado,
            "estado_label": self.estado_label,
            "solicitante": self.solicitante,
            "vehiculo": self.vehiculo_label,
            "fecha": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
        }

    def __repr__(self) -> str:
        return f"<AsistenciaEmergencia {self.id}:{self.estado}>"
