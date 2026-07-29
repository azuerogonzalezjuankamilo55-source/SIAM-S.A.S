from typing import TYPE_CHECKING

from database.db import db

if TYPE_CHECKING:
    from models.inventario import Inventario


class CategoriaInventario(db.Model):
    __tablename__ = "categorias_inventario"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(100), nullable=False, unique=True)
    descripcion: str | None = db.Column(db.Text)
    padre_id: int | None = db.Column(db.Integer, db.ForeignKey("categorias_inventario.id"), nullable=True)

    padre: "CategoriaInventario | None" = db.relationship(
        "CategoriaInventario", backref="hijas", remote_side="CategoriaInventario.id", lazy="select"
    )

    items: list["Inventario"] = db.relationship("Inventario", backref="categoria_obj", lazy="select")

    @property
    def path(self) -> str:
        parts = [self.nombre]
        p = self.padre
        while p:
            parts.append(p.nombre)
            p = p.padre
        return " > ".join(reversed(parts))

    def __repr__(self) -> str:
        return f"<CategoriaInventario {self.id}:{self.nombre}>"
