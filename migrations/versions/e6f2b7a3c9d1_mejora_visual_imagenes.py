"""mejora visual: imagenes servicios, fotos usuarios/mecanicos, historial fotos

Revision ID: e6f2b7a3c9d1
Revises: b7d3f1a2c9e4
Create Date: 2026-07-31 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f2b7a3c9d1'
down_revision = 'b7d3f1a2c9e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('servicios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('imagen_path', sa.String(length=300), nullable=True))

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('foto_path', sa.String(length=300), nullable=True))

    with op.batch_alter_table('mecanicos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('foto_path', sa.String(length=300), nullable=True))

    op.create_table(
        'historial_foto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('historial_vehiculo_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('path', sa.String(length=300), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['historial_vehiculo_id'], ['historial_vehiculo.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('historial_foto')

    with op.batch_alter_table('mecanicos', schema=None) as batch_op:
        batch_op.drop_column('foto_path')

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_column('foto_path')

    with op.batch_alter_table('servicios', schema=None) as batch_op:
        batch_op.drop_column('imagen_path')
