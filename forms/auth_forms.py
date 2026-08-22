from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional


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
        "Nombre completo",
        validators=[DataRequired(), Length(min=2, max=100)],
    )
    documento = StringField(
        "Documento de identidad",
        validators=[DataRequired(), Length(min=5, max=20)],
        render_kw={"placeholder": "Cédula o documento"},
    )
    correo = StringField(
        "Correo electrónico",
        validators=[DataRequired(), Email()],
    )
    telefono = StringField(
        "Teléfono",
        validators=[Optional(), Length(max=20)],
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirmar_password = PasswordField(
        "Confirmar contraseña",
        validators=[
            DataRequired(),
            EqualTo("password", message="Las contraseñas no coinciden."),
        ],
    )
    submit = SubmitField("Crear cuenta")


class AdminRegisterForm(FlaskForm):
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
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirmar_password = PasswordField(
        "Confirmar contraseña",
        validators=[
            DataRequired(),
            EqualTo("password", message="Las contraseñas no coinciden."),
        ],
    )
    submit = SubmitField("Crear cuenta administrativa")
