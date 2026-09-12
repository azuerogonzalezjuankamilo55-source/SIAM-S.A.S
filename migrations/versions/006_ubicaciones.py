"""ubicaciones_cliente para geolocalizacion en vivo

Revision ID: 006_ubicaciones
Revises: 005_vehiculo_cliente_campos
Create Date: 2026-09-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_ubicaciones'
down_revision = '005_vehiculo_cliente_campos'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ubicaciones_cliente',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cliente_id', sa.Integer(), sa.ForeignKey('clientes.id'), nullable=False),
        sa.Column('cita_id', sa.Integer(), sa.ForeignKey('citas.id'), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('sharing_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_ubicaciones_cliente_cliente_id', 'ubicaciones_cliente', ['cliente_id'])
    op.create_index('ix_ubicaciones_cliente_cita_id', 'ubicaciones_cliente', ['cita_id'])


def downgrade():
    op.drop_index('ix_ubicaciones_cliente_cita_id', table_name='ubicaciones_cliente')
    op.drop_index('ix_ubicaciones_cliente_cliente_id', table_name='ubicaciones_cliente')
    op.drop_table('ubicaciones_cliente')