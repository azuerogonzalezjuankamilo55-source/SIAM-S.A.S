from flask_wtf import FlaskForm
from wtforms import (
    IntegerField, SelectField, SubmitField, StringField, TextAreaField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length


class CotizacionForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    vehiculo_id = IntegerField("Vehículo", validators=[DataRequired()])
    sede_id = SelectField("Sede", coerce=int, validators=[Optional()])
    validez_dias = IntegerField("Días de validez", validators=[Optional(), NumberRange(min=1, max=365)], default=15)
    descripcion = TextAreaField("Descripción / alcance", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Guardar")


class CotizacionItemForm(FlaskForm):
    servicio_id = IntegerField("Servicio", validators=[DataRequired()])
    cantidad = IntegerField("Cantidad", validators=[DataRequired(), NumberRange(min=1, max=999)], default=1)
    submit = SubmitField("Agregar")


class GarantiaForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    vehiculo_id = IntegerField("Vehículo", validators=[DataRequired()])
    servicio_id = SelectField("Servicio", coerce=int, validators=[Optional()])
    descripcion = StringField("Descripción", validators=[DataRequired(), Length(max=500)])
    meses_validez = IntegerField("Meses de validez", validators=[DataRequired(), NumberRange(min=1, max=120)], default=3)
    submit = SubmitField("Registrar garantía")
