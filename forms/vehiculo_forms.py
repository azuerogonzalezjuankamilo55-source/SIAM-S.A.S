from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class VehiculoForm(FlaskForm):
    cliente_id = IntegerField("Cliente", validators=[DataRequired()])
    marca = StringField("Marca *", validators=[DataRequired(), Length(max=50)])
    modelo = StringField("Modelo *", validators=[DataRequired(), Length(max=50)])
    anio = IntegerField("Año", validators=[Optional()])
    placa = StringField("Placa *", validators=[DataRequired(), Length(max=20)])
    vin = StringField("VIN", validators=[Optional(), Length(max=17)])
    color = StringField("Color", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Guardar")
