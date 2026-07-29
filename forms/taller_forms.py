from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, TextAreaField, SubmitField
from wtforms.validators import Optional, Length, NumberRange, DataRequired


class TallerConfigForm(FlaskForm):
    nombre_taller = StringField("Nombre del taller *", validators=[DataRequired(), Length(max=200)])
    nit = StringField("NIT", validators=[Optional(), Length(max=30)])
    direccion = StringField("Dirección", validators=[Optional(), Length(max=300)])
    telefono = StringField("Teléfono", validators=[Optional(), Length(max=30)])
    email = StringField("Email", validators=[Optional(), Length(max=100)])
    regimen = StringField("Régimen", validators=[Optional(), Length(max=50)])
    prefijo_factura = StringField("Prefijo factura", validators=[Optional(), Length(max=10)])
    resolucion_dian = StringField("Resolución DIAN", validators=[Optional(), Length(max=50)])
    iva_porcentaje = DecimalField(
        "IVA %", places=2, default=19.00,
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )
    logo = FileField("Logo del taller", validators=[Optional(), FileAllowed(["jpg", "png", "jpeg", "svg"], "Solo imágenes")])
    submit = SubmitField("Guardar configuración")
