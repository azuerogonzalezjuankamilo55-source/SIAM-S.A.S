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

NIVELES_COMBUSTIBLE = ["Vacio", "1/4", "1/2", "3/4", "Lleno"]


class OrdenTrabajoForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    vehiculo_id = IntegerField("Vehículo", validators=[DataRequired()])
    mecanico_id = IntegerField("Mecánico", validators=[Optional()])
    fecha_ingreso = DateField("Fecha de Ingreso", validators=[DataRequired()])
    fecha_estimada_entrega = DateField("Fecha Estimada de Entrega", validators=[Optional()])
    diagnostico_inicial = StringField("Diagnóstico Inicial", validators=[Optional()])
    observaciones = StringField("Observaciones", validators=[Optional()])
    kms_ingreso = IntegerField("Kilometraje de Ingreso", validators=[Optional()])
    nivel_combustible_ingreso = SelectField(
        "Nivel de Combustible al Ingreso", choices=NIVELES_COMBUSTIBLE, validators=[Optional()]
    )
    submit = SubmitField("Guardar")


class CambiarEstadoForm(FlaskForm):
    estado = SelectField("Nuevo Estado", choices=ESTADOS_OT, validators=[DataRequired()])
    observacion = StringField("Observación", validators=[Optional()])
    submit = SubmitField("Cambiar Estado")
