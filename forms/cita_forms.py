from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, TimeField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

ESTADOS = [
    ("pendiente", "Pendiente"),
    ("en_proceso", "En Proceso"),
    ("completado", "Completado"),
    ("cancelado", "Cancelado"),
]


class CitaForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    vehiculo_id = IntegerField("Vehículo", validators=[DataRequired()])
    mecanico_id = IntegerField("Mecánico", validators=[Optional()])
    fecha = DateField("Fecha *", validators=[DataRequired()])
    hora = TimeField("Hora *", validators=[DataRequired()])
    estado = SelectField("Estado", choices=ESTADOS, default="pendiente")
    descripcion = StringField("Descripción", validators=[Optional()])
    submit = SubmitField("Guardar")
