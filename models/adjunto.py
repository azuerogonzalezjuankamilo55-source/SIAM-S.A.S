from database.db import db

TIPOS_ADJUNTO = ["imagen", "video", "pdf"]


class Adjunto(db.Model):
    __tablename__ = "adjuntos"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    usuario_id: int = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo: str = db.Column(db.String(20), nullable=False, default="imagen")
    nombre_original: str = db.Column(db.String(255), nullable=False)
    path: str = db.Column(db.String(300), nullable=False)
    mime: str | None = db.Column(db.String(100))
    tamano: int | None = db.Column(db.BigInteger)
    entidad_tipo: str | None = db.Column(db.String(30), index=True)
    entidad_id: int | None = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def es_imagen(self) -> bool:
        return self.tipo == "imagen"

    @property
    def es_video(self) -> bool:
        return self.tipo == "video"

    @property
    def es_pdf(self) -> bool:
        return self.tipo == "pdf"

    @property
    def tamano_legible(self) -> str:
        if not self.tamano:
            return "\u2014"
        kb = self.tamano / 1024
        if kb < 1024:
            return f"{kb:.0f} KB"
        return f"{kb / 1024:.1f} MB"

    def __repr__(self) -> str:
        return f"<Adjunto {self.id}:{self.nombre_original} tipo={self.tipo}>"
