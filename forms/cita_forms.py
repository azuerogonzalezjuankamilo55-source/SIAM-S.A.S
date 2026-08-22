from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, TimeField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

ESTADOS = [
    ("pendiente", "Pendiente"),
    ("confirmada", "Confirmada"),
    ("en_revision", "En revisión"),
    ("en_reparacion", "En reparación"),
    ("lista", "Lista"),
    ("entregada", "Entregada"),
    ("cancelado", "Cancelada"),
]


class CitaForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    vehiculo_id = IntegerField("Vehículo", validators=[DataRequired()])
    mecanico_id = IntegerField("Mecánico", validators=[Optional()])
    sede_id = SelectField("Sede", coerce=int, validators=[Optional()])
    servicio_id = SelectField("Servicio", coerce=int, validators=[Optional()])
    fecha = DateField("Fecha *", validators=[DataRequired()])
    hora = TimeField("Hora *", validators=[DataRequired()])
    estado = SelectField("Estado", choices=ESTADOS, default="pendiente")
    descripcion = StringField("Descripción", validators=[Optional()])
    submit = SubmitField("Guardar")
