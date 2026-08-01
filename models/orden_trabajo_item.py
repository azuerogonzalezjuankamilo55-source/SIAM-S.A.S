from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.orden_trabajo import OrdenTrabajo


class OrdenTrabajoItem(db.Model):
    __tablename__ = "ordenes_trabajo_items"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    orden_trabajo_id: int = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=False)
    descripcion: str = db.Column(db.String(200), nullable=False)
    completado: bool = db.Column(db.Boolean, nullable=False, default=False)
    tiempo_minutos: int | None = db.Column(db.Integer)
    posicion: int = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self) -> str:
        return f"<OTItem {self.id}:{self.descripcion[:30]} done={self.completado}>"
