"""alinear esquema con modelos (idempotente, PostgreSQL seguro)

Revision ID: d4e8f1a3c5b7
Revises: c2f8a4d6e1b7
Create Date: 2026-08-15 09:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "d4e8f1a3c5b7"
down_revision = "c2f8a4d6e1b7"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _index_exists(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [ix["name"] for ix in inspector.get_indexes(table)]
    return index in indexes


def upgrade():
    # ------------------------------------------------------------------
    # 1. usuarios.last_access_at — el modelo lo usa en login y NO existe.
    #    Esta es la causa raíz del InFailedSqlTransaction en producción:
    #    al hacer login, `usuario.last_access_at = datetime.now()` produce
    #    "column usuarios.last_access_at does not exist".
    # ------------------------------------------------------------------
    if not _column_exists("usuarios", "last_access_at"):
        op.add_column(
            "usuarios",
            sa.Column("last_access_at", sa.DateTime(), nullable=True),
        )

    # ------------------------------------------------------------------
    # 2. recordatorios: el modelo declara `vehiculo_id` con index=True
    #    (índice ix_recordatorios_vehiculo_id), pero la BD tiene el índice
    #    antiguo ix_recordatorios_vehiculo. Alineamos de forma idempotente.
    # ------------------------------------------------------------------
    if not _index_exists("recordatorios", "ix_recordatorios_vehiculo_id"):
        op.create_index(
            "ix_recordatorios_vehiculo_id",
            "recordatorios",
            ["vehiculo_id"],
            unique=False,
        )
    if _index_exists("recordatorios", "ix_recordatorios_vehiculo"):
        op.drop_index("ix_recordatorios_vehiculo", table_name="recordatorios")

    # ------------------------------------------------------------------
    # 3. citas: los modelos ya no declaran índices en sede_id/servicio_id.
    #    Eliminamos los obsoletos solo si existen (idempotente y seguro).
    # ------------------------------------------------------------------
    if _index_exists("citas", "ix_citas_sede_id"):
        op.drop_index("ix_citas_sede_id", table_name="citas")
    if _index_exists("citas", "ix_citas_servicio_id"):
        op.drop_index("ix_citas_servicio_id", table_name="citas")


def downgrade():
    # Restaurar estado anterior (solo si las estructuras existen)
    if _column_exists("usuarios", "last_access_at"):
        op.drop_column("usuarios", "last_access_at")
    if _index_exists("recordatorios", "ix_recordatorios_vehiculo_id"):
        op.drop_index("ix_recordatorios_vehiculo_id", table_name="recordatorios")
    if not _index_exists("recordatorios", "ix_recordatorios_vehiculo"):
        op.create_index(
            "ix_recordatorios_vehiculo",
            "recordatorios",
            ["vehiculo_id"],
            unique=False,
        )
    if not _index_exists("citas", "ix_citas_sede_id"):
        op.create_index("ix_citas_sede_id", "citas", ["sede_id"], unique=False)
    if not _index_exists("citas", "ix_citas_servicio_id"):
        op.create_index("ix_citas_servicio_id", "citas", ["servicio_id"], unique=False)