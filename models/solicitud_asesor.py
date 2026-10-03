from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.cliente import Cliente
    from models.vehiculo import Vehiculo


class SolicitudAsesor(db.Model):
    """Solicitud de asesoría creada por un cliente y atendida por el taller.

    Es una comunicación de negocio: no implica una emergencia ni una visita
    en camino, por eso vive en su propia tabla y no se mezcla con
    `asistencias_emergencia`.
    """

    __tablename__ = "solicitudes_asesor"
    __allow_unmapped__ = True

    TIPOS = ("asesoria", "soporte_tecnico", "informacion")
    TIPOS_LABELS = {
        "asesoria": "Asesoría comercial",
        "soporte_tecnico": "Soporte técnico",
        "informacion": "Información",
    }

    ESTADOS = ("pendiente", "en_atencion", "atendida", "cancelada")
    ESTADOS_LABELS = {
        "pendiente": "Pendiente",
        "en_atencion": "En atención",
        "atendida": "Atendida",
        "cancelada": "Cancelada",
    }

    #: Estados en los que la solicitud sigue viva (aun no terminada).
    ESTADOS_ABIERTOS = ("pendiente", "en_atencion")

    id: int = db.Column(db.Integer, primary_key=True)
    usuario_id: int | None = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True
    )
    cliente_id: int | None = db.Column(
        db.Integer, db.ForeignKey("clientes.id"), nullable=True, index=True
    )
    vehiculo_id: int | None = db.Column(
        db.Integer, db.ForeignKey("vehiculos.id"), nullable=True, index=True
    )
    cliente_nombre: str | None = db.Column(db.String(150))
    telefono: str | None = db.Column(db.String(20))
    tipo: str = db.Column(db.String(30), nullable=False, default="asesoria")
    asunto: str | None = db.Column(db.String(200))
    mensaje: str | None = db.Column(db.Text)
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente")
    respuesta: str | None = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    cliente: "Cliente | None" = db.relationship(
        "Cliente", backref=db.backref("solicitudes_asesor", lazy="select"), lazy="joined"
    )
    vehiculo: "Vehiculo | None" = db.relationship(
        "Vehiculo", backref=db.backref("solicitudes_asesor", lazy="select"), lazy="joined"
    )

    @property
    def estado_label(self) -> str:
        return self.ESTADOS_LABELS.get(self.estado, self.estado.replace("_", " ").capitalize())

    @property
    def tipo_label(self) -> str:
        return self.TIPOS_LABELS.get(self.tipo, self.tipo.capitalize())

    @property
    def esta_abierta(self) -> bool:
        return self.estado in self.ESTADOS_ABIERTOS

    @property
    def solicitante(self) -> str:
        """Nombre del cliente que pidió la asesoría."""
        if self.cliente_nombre:
            return self.cliente_nombre
        if self.cliente:
            return self.cliente.nombre
        return "Sin identificar"

    @property
    def vehiculo_label(self) -> str:
        """Descriptor del vehículo; vacío si la solicitud no tiene uno asociado."""
        if not self.vehiculo:
            return ""
        from services.vehiculo_service import VehiculoService

        return VehiculoService.descriptor(self.vehiculo)

    @property
    def placa(self) -> str:
        return (self.vehiculo.placa if self.vehiculo else "") or ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "tipo_label": self.tipo_label,
            "asunto": self.asunto or "",
            "mensaje": self.mensaje or "",
            "estado": self.estado,
            "estado_label": self.estado_label,
            "solicitante": self.solicitante,
            "vehiculo": self.vehiculo_label,
            "placa": self.placa,
            "telefono": self.telefono or "",
            "respuesta": self.respuesta or "",
            "fecha": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
        }

    def __repr__(self) -> str:
        return f"<SolicitudAsesor {self.id}:{self.estado}>"
