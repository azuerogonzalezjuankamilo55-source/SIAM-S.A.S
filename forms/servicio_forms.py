from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class ServicioForm(FlaskForm):
    nombre = StringField("Nombre *", validators=[DataRequired(), Length(max=100)])
    descripcion = StringField("Descripción", validators=[Optional()])
    precio_estimado = DecimalField(
        "Precio estimado",
        places=2,
        validators=[Optional()],
    )
    duracion_estimada = IntegerField("Duración (minutos)", validators=[Optional()])
    categoria = StringField("Categoría", validators=[Optional(), Length(max=50)])
    garantia_meses = IntegerField("Meses de garantía", validators=[Optional()])
    imagen = FileField("Imagen del servicio", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo imágenes JPG, PNG o WebP")])
    submit = SubmitField("Guardar")
