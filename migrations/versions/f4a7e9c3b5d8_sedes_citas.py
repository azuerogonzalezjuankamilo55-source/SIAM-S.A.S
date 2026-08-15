"""sedes y sede/servicio en citas

Revision ID: f4a7e9c3b5d8
Revises: d3b6e8f2a1c4
Create Date: 2026-08-14 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4a7e9c3b5d8'
down_revision = 'd3b6e8f2a1c4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sedes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=150), nullable=False),
    sa.Column('direccion', sa.String(length=300), nullable=True),
    sa.Column('telefono', sa.String(length=30), nullable=True),
    sa.Column('horario', sa.String(length=250), nullable=True),
    sa.Column('latitud', sa.Float(), nullable=True),
    sa.Column('longitud', sa.Float(), nullable=True),
    sa.Column('servicios', sa.Text(), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('citas', sa.Column('sede_id', sa.Integer(), nullable=True))
    op.add_column('citas', sa.Column('servicio_id', sa.Integer(), nullable=True))
    op.create_index('ix_citas_sede_id', 'citas', ['sede_id'], unique=False)
    op.create_index('ix_citas_servicio_id', 'citas', ['servicio_id'], unique=False)
    op.create_foreign_key(None, 'citas', 'sedes', ['sede_id'], ['id'])
    op.create_foreign_key(None, 'citas', 'servicios', ['servicio_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'citas', type_='foreignkey')
    op.drop_constraint(None, 'citas', type_='foreignkey')
    op.drop_index('ix_citas_servicio_id', table_name='citas')
    op.drop_index('ix_citas_sede_id', table_name='citas')
    op.drop_column('citas', 'servicio_id')
    op.drop_column('citas', 'sede_id')
    op.drop_table('sedes')
