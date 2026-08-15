"""adjuntos

Revision ID: d3b6e8f2a1c4
Revises: c1a9d4f2e6b8
Create Date: 2026-08-14 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3b6e8f2a1c4'
down_revision = 'c1a9d4f2e6b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('adjuntos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('nombre_original', sa.String(length=255), nullable=False),
    sa.Column('path', sa.String(length=300), nullable=False),
    sa.Column('mime', sa.String(length=100), nullable=True),
    sa.Column('tamano', sa.BigInteger(), nullable=True),
    sa.Column('entidad_tipo', sa.String(length=30), nullable=True),
    sa.Column('entidad_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_adjuntos_usuario', 'adjuntos', ['usuario_id'], unique=False)
    op.create_index('ix_adjuntos_entidad_tipo', 'adjuntos', ['entidad_tipo'], unique=False)
    op.create_index('ix_adjuntos_entidad_id', 'adjuntos', ['entidad_id'], unique=False)


def downgrade():
    op.drop_index('ix_adjuntos_entidad_id', table_name='adjuntos')
    op.drop_index('ix_adjuntos_entidad_tipo', table_name='adjuntos')
    op.drop_index('ix_adjuntos_usuario', table_name='adjuntos')
    op.drop_table('adjuntos')
