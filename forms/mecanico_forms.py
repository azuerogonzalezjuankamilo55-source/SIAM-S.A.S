from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class MecanicoForm(FlaskForm):
    nombre = StringField("Nombre *", validators=[DataRequired(), Length(max=100)])
    telefono = StringField("Teléfono", validators=[Optional(), Length(max=20)])
    correo = StringField("Correo electrónico", validators=[Optional(), Length(max=120)])
    especialidad = StringField("Especialidad", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Guardar")
