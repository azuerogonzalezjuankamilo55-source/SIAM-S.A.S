"""vehiculo tipo kilometraje motor combustible

Revision ID: 005
Revises: d4e8f1a3c5b7
Create Date: 2026-08-22 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_vehiculo_cliente_campos'
down_revision = 'd4e8f1a3c5b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vehiculos', sa.Column('tipo', sa.String(length=10), nullable=False, server_default='carro'))
    op.add_column('vehiculos', sa.Column('kilometraje', sa.Integer(), nullable=True))
    op.add_column('vehiculos', sa.Column('motor', sa.String(length=50), nullable=True))
    op.add_column('vehiculos', sa.Column('combustible', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('vehiculos', 'combustible')
    op.drop_column('vehiculos', 'motor')
    op.drop_column('vehiculos', 'kilometraje')
    op.drop_column('vehiculos', 'tipo')
