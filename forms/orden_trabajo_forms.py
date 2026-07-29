from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

ESTADOS_OT = [
    ("recibido", "Recibido"),
    ("diagnostico", "Diagnóstico"),
    ("esperando_repuestos", "Esperando Repuestos"),
    ("en_reparacion", "En Reparación"),
    ("listo_entrega", "Listo para Entrega"),
    ("entregado", "Entregado"),
]


class OrdenTrabajoForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    vehiculo_id = IntegerField("Vehículo", validators=[DataRequired()])
    mecanico_id = IntegerField("Mecánico", validators=[Optional()])
    fecha_ingreso = DateField("Fecha de Ingreso", validators=[DataRequired()])
    fecha_estimada_entrega = DateField("Fecha Estimada de Entrega", validators=[Optional()])
    diagnostico_inicial = StringField("Diagnóstico Inicial", validators=[Optional()])
    observaciones = StringField("Observaciones", validators=[Optional()])
    submit = SubmitField("Guardar")


class CambiarEstadoForm(FlaskForm):
    estado = SelectField("Nuevo Estado", choices=ESTADOS_OT, validators=[DataRequired()])
    observacion = StringField("Observación", validators=[Optional()])
    submit = SubmitField("Cambiar Estado")
