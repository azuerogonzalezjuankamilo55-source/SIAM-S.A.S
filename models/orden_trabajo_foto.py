from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.orden_trabajo import OrdenTrabajo


class OrdenTrabajoFoto(db.Model):
    __tablename__ = "ordenes_trabajo_fotos"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    orden_trabajo_id: int = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=False)
    path: str = db.Column(db.String(300), nullable=False)
    descripcion: str | None = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self) -> str:
        return f"<OTFoto {self.id}:{self.path}>"
