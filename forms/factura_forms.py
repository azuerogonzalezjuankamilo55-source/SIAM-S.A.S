from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import (
    DecimalField, SelectField, SubmitField, FieldList, HiddenField,
    StringField, TextAreaField, IntegerField,
)
from wtforms.validators import Optional, NumberRange, Length, DataRequired

from models.factura import METODOS_PAGO


class FacturaForm(FlaskForm):
    servicio_ids = FieldList(HiddenField("servicio_id"), min_entries=1)
    precios = FieldList(DecimalField("precio_unitario", places=2), min_entries=1)
    cantidades = FieldList(DecimalField("cantidad", places=0, default=1), min_entries=1)
    descuento = DecimalField(
        "Descuento",
        places=2,
        default=0,
        validators=[Optional(), NumberRange(min=0)],
    )
    metodo_pago = SelectField(
        "Método de pago",
        choices=METODOS_PAGO,
        default="Efectivo",
    )
    notas = TextAreaField("Notas", validators=[Optional()])
    submit = SubmitField("Generar Factura")


class PagoForm(FlaskForm):
    monto = DecimalField("Monto *", places=2, validators=[DataRequired(), NumberRange(min=1)])
    metodo_pago = SelectField(
        "Método de pago *",
        choices=METODOS_PAGO,
        default="Efectivo",
    )
    referencia = StringField("Referencia", validators=[Optional(), Length(max=100)])
    notas = TextAreaField("Notas", validators=[Optional()])
    submit = SubmitField("Registrar Pago")


class LogoForm(FlaskForm):
    logo = StringField("URL del logo", validators=[Optional(), Length(max=300)])
    submit = SubmitField("Guardar")
