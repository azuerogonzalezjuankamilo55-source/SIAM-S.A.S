from decimal import Decimal

from database.db import db


class ConfiguracionTaller(db.Model):
    __tablename__ = "configuracion_taller"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    nombre_taller: str = db.Column(db.String(200), nullable=False, default="Mi Taller")
    nit: str | None = db.Column(db.String(30))
    direccion: str | None = db.Column(db.String(300))
    telefono: str | None = db.Column(db.String(30))
    email: str | None = db.Column(db.String(100))
    logo_path: str | None = db.Column(db.String(300))
    regimen: str = db.Column(db.String(50), default="Común")
    prefijo_factura: str = db.Column(db.String(10), default="FAC")
    resolucion_dian: str | None = db.Column(db.String(50))
    iva_porcentaje: Decimal = db.Column(db.Numeric(4, 2), nullable=False, default=Decimal("19.00"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    @classmethod
    def get_config(cls) -> "ConfiguracionTaller":
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                raise RuntimeError("No se pudo crear la configuración del taller") from e
        return config

    @property
    def iva_rate(self) -> Decimal:
        return self.iva_porcentaje / Decimal("100")

    def __repr__(self) -> str:
        return f"<ConfiguracionTaller {self.id}:{self.nombre_taller}>"
