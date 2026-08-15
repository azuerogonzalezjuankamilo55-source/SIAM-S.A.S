"""ordenes de trabajo

Revision ID: 002
Revises: 001
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ordenes_trabajo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), nullable=False),
        sa.Column("mecanico_id", sa.Integer(), nullable=True),
        sa.Column("fecha_ingreso", sa.Date(), nullable=False),
        sa.Column("fecha_estimada_entrega", sa.Date(), nullable=True),
        sa.Column("diagnostico_inicial", sa.Text(), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(30), nullable=False, server_default="recibido"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mecanico_id"], ["mecanicos.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "ordenes_trabajo_historial",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orden_trabajo_id", sa.Integer(), nullable=False),
        sa.Column("estado_anterior", sa.String(30), nullable=True),
        sa.Column("estado_nuevo", sa.String(30), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["orden_trabajo_id"], ["ordenes_trabajo.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
    )


def downgrade():
    op.drop_table("ordenes_trabajo_historial")
    op.drop_table("ordenes_trabajo")
