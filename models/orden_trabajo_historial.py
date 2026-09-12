from database.db import db
from models.orden_trabajo import COLORES_ESTADO_OT


class OrdenTrabajoHistorial(db.Model):
    __tablename__ = "ordenes_trabajo_historial"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    orden_trabajo_id: int = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=False)
    estado_anterior: str | None = db.Column(db.String(30))
    estado_nuevo: str = db.Column(db.String(30), nullable=False)
    observacion: str | None = db.Column(db.Text)
    usuario_id: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def estado_color(self) -> str:
        return COLORES_ESTADO_OT.get(self.estado_nuevo, "secondary")

    def __repr__(self) -> str:
        return f"<OTHistorial {self.id}:{self.estado_anterior}->{self.estado_nuevo}>"
