from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from models.categoria_inventario import CategoriaInventario


def _coerce_nullable_int(value: str | int | None) -> int | None:
    if value is None or value == "" or value == "None":
        return None
    return int(value)


def _categoria_choices() -> list[tuple[str, str]]:
    cats = CategoriaInventario.query.order_by(CategoriaInventario.nombre).all()
    return [("", "Seleccione categoría...")] + [(str(c.id), c.path) for c in cats]


class InventarioForm(FlaskForm):
    nombre = StringField("Nombre *", validators=[DataRequired(), Length(max=150)])
    descripcion = TextAreaField("Descripción", validators=[Optional()])
    sku = StringField("Código SKU", validators=[Optional(), Length(max=50)])
    codigo_barras = StringField("Código de barras", validators=[Optional(), Length(max=100)])
    ubicacion = StringField("Ubicación", validators=[Optional(), Length(max=50)])
    cantidad = IntegerField("Cantidad", default=0, validators=[Optional(), NumberRange(min=0)])
    precio_compra = DecimalField("Costo", places=2, validators=[Optional()])
    precio_venta = DecimalField("Precio venta", places=2, validators=[Optional()])
    proveedor = StringField("Proveedor", validators=[Optional(), Length(max=100)])
    categoria_id = SelectField("Categoría", coerce=_coerce_nullable_int, validators=[Optional()])
    stock_minimo = IntegerField("Stock mínimo", default=0, validators=[Optional(), NumberRange(min=0)])
    stock_critico = IntegerField("Stock crítico", default=0, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Guardar")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.categoria_id.choices = _categoria_choices()


class MovimientoInventarioForm(FlaskForm):
    tipo = SelectField(
        "Tipo de movimiento",
        choices=[
            ("entrada", "Entrada"),
            ("salida", "Salida"),
            ("ajuste", "Ajuste"),
        ],
        validators=[DataRequired()],
    )
    cantidad = IntegerField("Cantidad", validators=[DataRequired(), NumberRange(min=1)])
    motivo = TextAreaField("Motivo / Observación", validators=[Optional()])
    referencia = StringField("Referencia (factura, orden, etc.)", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Registrar")


class CategoriaInventarioForm(FlaskForm):
    nombre = StringField("Nombre *", validators=[DataRequired(), Length(max=100)])
    descripcion = TextAreaField("Descripción", validators=[Optional()])
    padre_id = SelectField("Categoría padre", coerce=_coerce_nullable_int, validators=[Optional()])
    submit = SubmitField("Guardar")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.padre_id.choices = [("", "Ninguna (categoría raíz)")] + _categoria_choices()
