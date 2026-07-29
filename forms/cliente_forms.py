from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class ClienteForm(FlaskForm):
    nombre = StringField(
        "Nombre *",
        validators=[DataRequired(), Length(max=150)],
    )
    telefono = StringField(
        "Teléfono",
        validators=[Optional(), Length(max=20)],
    )
    correo = StringField(
        "Correo electrónico",
        validators=[Optional(), Length(max=120)],
    )
    direccion = StringField(
        "Dirección",
        validators=[Optional()],
    )
    cedula = StringField(
        "Cédula",
        validators=[Optional(), Length(max=20)],
    )
    submit = SubmitField("Guardar")
