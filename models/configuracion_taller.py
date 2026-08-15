from decimal import Decimal

from database.db import db


class ConfiguracionTaller(db.Model):
    __tablename__ = "configuracion_taller"
    __allow_unmapped__ = True

    id: int = db.Column(db.Integer, primary_key=True)
    # --- Empresa / contacto ---
    nombre_taller: str = db.Column(db.String(200), nullable=False, default="Mi Taller")
    nit: str | None = db.Column(db.String(30))
    ciudad: str | None = db.Column(db.String(100))
    direccion: str | None = db.Column(db.String(300))
    telefono: str | None = db.Column(db.String(30))
    whatsapp: str | None = db.Column(db.String(30))
    email: str | None = db.Column(db.String(100))
    sitio_web: str | None = db.Column(db.String(200))
    facebook: str | None = db.Column(db.String(200))
    instagram: str | None = db.Column(db.String(200))
    twitter: str | None = db.Column(db.String(200))
    linkedin: str | None = db.Column(db.String(200))
    logo_path: str | None = db.Column(db.String(300))
    regimen: str = db.Column(db.String(50), default="Común")
    prefijo_factura: str = db.Column(db.String(10), default="FAC")
    resolucion_dian: str | None = db.Column(db.String(50))
    iva_porcentaje: Decimal = db.Column(db.Numeric(4, 2), nullable=False, default=Decimal("19.00"))
    # --- Apariencia (colores HEX validados) ---
    color_primario: str | None = db.Column(db.String(7), default="#2563EB")
    color_primario_fuerte: str | None = db.Column(db.String(7), default="#1D4ED8")
    color_primario_soft: str | None = db.Column(db.String(7), default="#DBEAFE")
    color_acento: str | None = db.Column(db.String(7), default="#0F766E")
    # --- Citas y horarios ---
    citas_intervalo_min: int = db.Column(db.Integer, nullable=False, default=30)
    citas_min_anticipacion_horas: int = db.Column(db.Integer, nullable=False, default=0)
    citas_cancelar_limite_horas: int = db.Column(db.Integer, nullable=False, default=0)
    # --- Notificaciones ---
    notif_email: bool = db.Column(db.Boolean, nullable=False, default=True)
    notif_sms: bool = db.Column(db.Boolean, nullable=False, default=False)
    notif_whatsapp: bool = db.Column(db.Boolean, nullable=False, default=False)
    notif_recordatorio_dias: int = db.Column(db.Integer, nullable=False, default=7)
    # --- Asistente IA ---
    ia_activado: bool = db.Column(db.Boolean, nullable=False, default=True)
    ia_nombre: str | None = db.Column(db.String(100), default="SIAM")
    ia_tono: str | None = db.Column(db.String(50), default="Profesional")
    ia_mensaje_bienvenida: str | None = db.Column(db.Text)
    ia_preguntas_sugeridas: str | None = db.Column(db.Text, comment="Lista de preguntas en JSON")
    ia_contacto: str | None = db.Column(db.String(200))
    ia_mensaje_emergencia: str | None = db.Column(db.Text)
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
