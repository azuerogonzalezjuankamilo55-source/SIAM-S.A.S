"""solicitudes_asesor: comunicacion cliente -> administracion

Revision ID: h9n4p7q2r6t1
Revises: g7h2k9m4p1q3
Create Date: 2026-10-02 00:00:00.000000

Crea la tabla de solicitudes de asesoría. Es independiente de
`asistencias_emergencia`: una asesoría es una comunicación de negocio y no
implica una emergencia ni una visita en camino, así que no comparte estados
ni panel con las asistencias de urgencia.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h9n4p7q2r6t1"
down_revision = "g7h2k9m4p1q3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "solicitudes_asesor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=True),
        sa.Column("vehiculo_id", sa.Integer(), sa.ForeignKey("vehiculos.id"), nullable=True),
        sa.Column("cliente_nombre", sa.String(length=150), nullable=True),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("tipo", sa.String(length=30), nullable=False, server_default="asesoria"),
        sa.Column("asunto", sa.String(length=200), nullable=True),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("respuesta", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_solicitudes_asesor_usuario_id", "solicitudes_asesor", ["usuario_id"])
    op.create_index("ix_solicitudes_asesor_cliente_id", "solicitudes_asesor", ["cliente_id"])
    op.create_index("ix_solicitudes_asesor_vehiculo_id", "solicitudes_asesor", ["vehiculo_id"])
    op.create_index("ix_solicitudes_asesor_created_at", "solicitudes_asesor", ["created_at"])


def downgrade():
    op.drop_index("ix_solicitudes_asesor_created_at", table_name="solicitudes_asesor")
    op.drop_index("ix_solicitudes_asesor_vehiculo_id", table_name="solicitudes_asesor")
    op.drop_index("ix_solicitudes_asesor_cliente_id", table_name="solicitudes_asesor")
    op.drop_index("ix_solicitudes_asesor_usuario_id", table_name="solicitudes_asesor")
    op.drop_table("solicitudes_asesor")
