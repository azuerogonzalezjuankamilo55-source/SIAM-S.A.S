from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    correo = StringField(
        "Correo electrónico",
        validators=[DataRequired(), Email()],
        render_kw={"placeholder": "admin@siam.com"},
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=4)],
        render_kw={"placeholder": "••••••••"},
    )
    submit = SubmitField("Ingresar")


class RegisterForm(FlaskForm):
    nombre = StringField(
        "Nombre",
        validators=[DataRequired(), Length(min=2, max=100)],
    )
    correo = StringField(
        "Correo electrónico",
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=4, max=128)],
    )
    submit = SubmitField("Registrarse")
