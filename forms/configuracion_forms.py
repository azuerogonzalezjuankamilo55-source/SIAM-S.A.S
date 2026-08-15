import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def validar_color_hex(_form: FlaskForm, field) -> None:
    if not field.data:
        return
    valor = field.data.strip()
    if not valor.startswith("#"):
        valor = "#" + valor
    if not HEX_RE.match(valor):
        raise ValidationError("Debe ser un color hexadecimal válido (#RRGGBB).")


def _color_field(label: str, default: str) -> StringField:
    return StringField(
        label,
        validators=[Optional(), Length(max=7), validar_color_hex],
        default=default,
    )


class EmpresaConfigForm(FlaskForm):
    nombre_taller = StringField("Nombre del taller *", validators=[DataRequired(), Length(max=200)])
    nit = StringField("NIT", validators=[Optional(), Length(max=30)])
    ciudad = StringField("Ciudad", validators=[Optional(), Length(max=100)])
    direccion = StringField("Dirección", validators=[Optional(), Length(max=300)])
    telefono = StringField("Teléfono", validators=[Optional(), Length(max=30)])
    whatsapp = StringField("WhatsApp", validators=[Optional(), Length(max=30)])
    email = StringField("Email", validators=[Optional(), Length(max=100)])
    sitio_web = StringField("Sitio web", validators=[Optional(), Length(max=200)])
    facebook = StringField("Facebook", validators=[Optional(), Length(max=200)])
    instagram = StringField("Instagram", validators=[Optional(), Length(max=200)])
    twitter = StringField("X (Twitter)", validators=[Optional(), Length(max=200)])
    linkedin = StringField("LinkedIn", validators=[Optional(), Length(max=200)])
    regimen = StringField("Régimen", validators=[Optional(), Length(max=50)])
    prefijo_factura = StringField("Prefijo factura", validators=[Optional(), Length(max=10)])
    resolucion_dian = StringField("Resolución DIAN", validators=[Optional(), Length(max=50)])
    iva_porcentaje = DecimalField(
        "IVA %", places=2, default=19.00,
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )
    logo = FileField(
        "Logo del taller",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo imágenes JPG, PNG o WebP")],
    )
    submit = SubmitField("Guardar")


class AparienciaForm(FlaskForm):
    color_primario = _color_field("Color principal", "#2563EB")
    color_primario_fuerte = _color_field("Color principal (intenso)", "#1D4ED8")
    color_primario_soft = _color_field("Color principal (suave)", "#DBEAFE")
    color_acento = _color_field("Color de acento", "#0F766E")
    submit = SubmitField("Guardar")


class CitasConfigForm(FlaskForm):
    citas_intervalo_min = IntegerField(
        "Duración de cada cita (minutos)", default=30,
        validators=[DataRequired(), NumberRange(min=15, max=240)],
    )
    citas_min_anticipacion_horas = IntegerField(
        "Anticipación mínima para agendar (horas, 0 = sin límite)", default=0,
        validators=[DataRequired(), NumberRange(min=0, max=720)],
    )
    citas_cancelar_limite_horas = IntegerField(
        "Horas de antelación para cancelar (0 = sin límite)", default=0,
        validators=[DataRequired(), NumberRange(min=0, max=720)],
    )
    submit = SubmitField("Guardar")


class NotificacionesConfigForm(FlaskForm):
    notif_email = BooleanField("Notificaciones por email", default=True)
    notif_sms = BooleanField("Notificaciones por SMS", default=False)
    notif_whatsapp = BooleanField("Notificaciones por WhatsApp", default=False)
    notif_recordatorio_dias = IntegerField(
        "Días de antelación para recordatorios", default=7,
        validators=[DataRequired(), NumberRange(min=1, max=90)],
    )
    submit = SubmitField("Guardar")


class IAConfigForm(FlaskForm):
    ia_activado = BooleanField("Asistente virtual activo", default=True)
    ia_nombre = StringField("Nombre del asistente", validators=[Optional(), Length(max=100)])
    ia_tono = SelectField(
        "Tono de respuesta",
        choices=[
            ("Profesional", "Profesional"),
            ("Amigable", "Amigable"),
            ("Técnico", "Técnico"),
        ],
        validators=[Optional()],
    )
    ia_mensaje_bienvenida = TextAreaField(
        "Mensaje de bienvenida", validators=[Optional(), Length(max=2000)],
        description="Si se deja vacío se usa el mensaje por defecto del sistema.",
    )
    ia_contacto = StringField("Contacto / referencia", validators=[Optional(), Length(max=200)])
    ia_mensaje_emergencia = TextAreaField(
        "Mensaje de emergencia", validators=[Optional(), Length(max=2000)],
    )
    ia_preguntas_sugeridas = TextAreaField(
        "Preguntas sugeridas (una por línea)", validators=[Optional(), Length(max=3000)],
        description="Se muestran como atajos al inicio del chat.",
    )
    submit = SubmitField("Guardar")
