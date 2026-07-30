from database.db import db


class AsistenciaEmergencia(db.Model):
    __tablename__ = "asistencias_emergencia"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    usuario_id: int | None = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    cliente_nombre: str | None = db.Column(db.String(150))
    telefono: str | None = db.Column(db.String(20))
    descripcion: str | None = db.Column(db.Text)
    latitud: float | None = db.Column(db.Float)
    longitud: float | None = db.Column(db.Float)
    precision_metros: float | None = db.Column(db.Float)
    estado: str = db.Column(db.String(20), nullable=False, default="pendiente")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    def __repr__(self) -> str:
        return f"<AsistenciaEmergencia {self.id}:{self.estado}>"
