from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, IntegerField, DateField, TimeField, SelectField,
    TextAreaField, PasswordField, SubmitField,
)
from wtforms.validators import DataRequired, Length, Optional, Email, EqualTo


class SolicitarCitaForm(FlaskForm):
    vehiculo_id = IntegerField("Vehículo *", validators=[DataRequired()])
    sede_id = SelectField("Sede *", coerce=int, validators=[DataRequired()])
    servicio_id = SelectField("Servicio", coerce=int, validators=[Optional()])
    fecha = DateField("Fecha *", validators=[DataRequired()])
    hora = TimeField("Hora *", validators=[DataRequired()])
    descripcion = TextAreaField("Descripción del problema", validators=[Optional(), Length(max=1000)])
    adjuntos = FileField(
        "Fotos, videos o PDF (opcional)",
        validators=[Optional()],
        render_kw={"multiple": True, "accept": ".jpg,.jpeg,.png,.webp,.mp4,.pdf"},
    )
    submit = SubmitField("Solicitar cita")


class PerfilForm(FlaskForm):
    nombre = StringField("Nombre *", validators=[DataRequired(), Length(max=150)])
    telefono = StringField("Teléfono", validators=[Optional(), Length(max=20)])
    correo = StringField("Correo electrónico", validators=[Optional(), Email(), Length(max=120)])
    direccion = StringField("Dirección", validators=[Optional(), Length(max=300)])
    foto = FileField("Foto de perfil", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo imágenes JPG, PNG o WebP")])
    submit = SubmitField("Guardar cambios")


class CambiarPasswordForm(FlaskForm):
    password_actual = PasswordField("Contraseña actual *", validators=[DataRequired()])
    nueva_password = PasswordField(
        "Nueva contraseña *",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirmar = PasswordField(
        "Confirmar nueva contraseña *",
        validators=[DataRequired(), EqualTo("nueva_password", message="Las contraseñas no coinciden")],
    )
    submit = SubmitField("Cambiar contraseña")
