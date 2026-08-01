from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.historial_vehiculo import HistorialVehiculo

TIPOS_FOTO_HISTORIAL = ["antes", "durante", "despues"]

TIPOS_FOTO_HISTORIAL_LABELS = {
    "antes": "Antes",
    "durante": "Durante",
    "despues": "Después",
}


class HistorialFoto(db.Model):
    __tablename__ = "historial_foto"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    historial_vehiculo_id: int = db.Column(
        db.Integer, db.ForeignKey("historial_vehiculo.id"), nullable=False
    )
    tipo: str = db.Column(db.String(20), nullable=False, default="antes")
    path: str = db.Column(db.String(300), nullable=False)
    descripcion: str | None = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    historial: "HistorialVehiculo" = db.relationship(
        "HistorialVehiculo", lazy="joined", overlaps="fotos"
    )

    @property
    def tipo_label(self) -> str:
        return TIPOS_FOTO_HISTORIAL_LABELS.get(self.tipo, self.tipo)

    def __repr__(self) -> str:
        return f"<HistorialFoto {self.id}:{self.tipo} historial={self.historial_vehiculo_id}>"
