"""agregar columnas faltantes a configuracion_taller (idempotente)

Revision ID: c2f8a4d6e1b7
Revises: b5d7e9a2c1f6
Create Date: 2026-08-15 02:04:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# Identificadores de Alembic
revision = "c2f8a4d6e1b7"
down_revision = "b5d7e9a2c1f6"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    """Verifica si una columna ya existe en la tabla (idempotencia)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    """Agrega una columna solo si no existe (idempotente)."""
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def upgrade():
    # --- Empresa / contacto (columnas que el modelo espera y no existían) ---
    _add_column_if_missing("configuracion_taller", sa.Column("ciudad", sa.String(length=100), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("whatsapp", sa.String(length=30), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("sitio_web", sa.String(length=200), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("facebook", sa.String(length=200), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("instagram", sa.String(length=200), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("twitter", sa.String(length=200), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("linkedin", sa.String(length=200), nullable=True))

    # --- Apariencia (colores HEX) ---
    _add_column_if_missing("configuracion_taller", sa.Column("color_primario", sa.String(length=7), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("color_primario_fuerte", sa.String(length=7), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("color_primario_soft", sa.String(length=7), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("color_acento", sa.String(length=7), nullable=True))

    # --- Asistente IA ---
    _add_column_if_missing("configuracion_taller", sa.Column("ia_nombre", sa.String(length=100), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("ia_tono", sa.String(length=50), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("ia_mensaje_bienvenida", sa.Text(), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("ia_preguntas_sugeridas", sa.Text(), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("ia_contacto", sa.String(length=200), nullable=True))
    _add_column_if_missing("configuracion_taller", sa.Column("ia_mensaje_emergencia", sa.Text(), nullable=True))

    # --- Usuario: último acceso (el modelo lo espera y ninguna migración lo agrega) ---
    _add_column_if_missing("usuarios", sa.Column("last_access_at", sa.DateTime(), nullable=True))


def downgrade():
    # Solo elimina columnas si existen (idempotente)
    for col in [
        "ia_mensaje_emergencia",
        "ia_contacto",
        "ia_preguntas_sugeridas",
        "ia_mensaje_bienvenida",
        "ia_tono",
        "ia_nombre",
        "color_acento",
        "color_primario_soft",
        "color_primario_fuerte",
        "color_primario",
        "linkedin",
        "twitter",
        "instagram",
        "facebook",
        "sitio_web",
        "whatsapp",
        "ciudad",
    ]:
        if _column_exists("configuracion_taller", col):
            op.drop_column("configuracion_taller", col)

    if _column_exists("usuarios", "last_access_at"):
        op.drop_column("usuarios", "last_access_at")