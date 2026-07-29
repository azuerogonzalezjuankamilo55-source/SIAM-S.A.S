from database.db import db


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

    def __repr__(self) -> str:
        return f"<OTHistorial {self.id}:{self.estado_anterior}->{self.estado_nuevo}>"
