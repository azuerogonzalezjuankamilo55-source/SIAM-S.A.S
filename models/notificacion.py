from database.db import db

TIPOS_NOTIFICACION = [
    "cita",
    "orden",
    "factura",
    "cotizacion",
    "garantia",
    "recordatorio",
    "pago",
    "sistema",
]

TIPOS_NOTIFICACION_LABELS = {
    "cita": "Cita",
    "orden": "Orden de trabajo",
    "factura": "Factura",
    "cotizacion": "Cotización",
    "garantia": "Garantía",
    "recordatorio": "Recordatorio",
    "pago": "Pago",
    "sistema": "Sistema",
}


class Notificacion(db.Model):
    __tablename__ = "notificaciones"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    usuario_id: int = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo: str = db.Column(db.String(30), nullable=False, default="sistema")
    titulo: str = db.Column(db.String(200), nullable=False)
    mensaje: str | None = db.Column(db.Text)
    url: str | None = db.Column(db.String(300))
    leida: bool = db.Column(db.Boolean, nullable=False, default=False, index=True)
    leida_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)

    @property
    def tipo_label(self) -> str:
        return TIPOS_NOTIFICACION_LABELS.get(self.tipo, self.tipo.replace("_", " ").capitalize())

    def __repr__(self) -> str:
        return f"<Notificacion {self.id}:{self.titulo} usuario={self.usuario_id} leida={self.leida}>"
