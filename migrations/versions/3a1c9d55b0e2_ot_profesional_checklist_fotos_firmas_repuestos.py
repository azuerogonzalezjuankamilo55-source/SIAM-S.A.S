"""ot profesional checklist fotos firmas repuestos

Revision ID: 3a1c9d55b0e2
Revises: 77ac884306b6
Create Date: 2026-07-31 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a1c9d55b0e2'
down_revision = '77ac884306b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ordenes_trabajo_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('orden_trabajo_id', sa.Integer(), nullable=False),
        sa.Column('descripcion', sa.String(length=200), nullable=False),
        sa.Column('completado', sa.Boolean(), nullable=False),
        sa.Column('tiempo_minutos', sa.Integer(), nullable=True),
        sa.Column('posicion', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['orden_trabajo_id'], ['ordenes_trabajo.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'ordenes_trabajo_fotos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('orden_trabajo_id', sa.Integer(), nullable=False),
        sa.Column('path', sa.String(length=300), nullable=False),
        sa.Column('descripcion', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['orden_trabajo_id'], ['ordenes_trabajo.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'ordenes_trabajo_repuestos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('orden_trabajo_id', sa.Integer(), nullable=False),
        sa.Column('inventario_id', sa.Integer(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('precio_unitario', sa.Numeric(10, 2), nullable=False),
        sa.Column('nota', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['inventario_id'], ['inventario.id'], ),
        sa.ForeignKeyConstraint(['orden_trabajo_id'], ['ordenes_trabajo.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ordenes_trabajo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kms_ingreso', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('nivel_combustible_ingreso', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('kms_salida', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('nivel_combustible_salida', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('fecha_entrega', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('firma_mecanico_path', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('firma_cliente_path', sa.String(length=300), nullable=True))


def downgrade():
    with op.batch_alter_table('ordenes_trabajo', schema=None) as batch_op:
        batch_op.drop_column('firma_cliente_path')
        batch_op.drop_column('firma_mecanico_path')
        batch_op.drop_column('fecha_entrega')
        batch_op.drop_column('nivel_combustible_salida')
        batch_op.drop_column('kms_salida')
        batch_op.drop_column('nivel_combustible_ingreso')
        batch_op.drop_column('kms_ingreso')

    op.drop_table('ordenes_trabajo_repuestos')
    op.drop_table('ordenes_trabajo_fotos')
    op.drop_table('ordenes_trabajo_items')
