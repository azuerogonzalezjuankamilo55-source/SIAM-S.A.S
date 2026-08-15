"""cotizaciones y garantias

Revision ID: a8c4d2f6e1b9
Revises: f4a7e9c3b5d8
Create Date: 2026-08-14 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8c4d2f6e1b9'
down_revision = 'f4a7e9c3b5d8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cotizaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('numero', sa.String(length=20), nullable=False),
    sa.Column('cliente_id', sa.Integer(), nullable=False),
    sa.Column('vehiculo_id', sa.Integer(), nullable=False),
    sa.Column('sede_id', sa.Integer(), nullable=True),
    sa.Column('orden_trabajo_id', sa.Integer(), nullable=True),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=True),
    sa.Column('validez_dias', sa.Integer(), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('iva_porcentaje', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('iva', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('descuento', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], ),
    sa.ForeignKeyConstraint(['orden_trabajo_id'], ['ordenes_trabajo.id'], ),
    sa.ForeignKeyConstraint(['sede_id'], ['sedes.id'], ),
    sa.ForeignKeyConstraint(['vehiculo_id'], ['vehiculos.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('numero')
    )
    op.create_index('ix_cotizaciones_cliente_id', 'cotizaciones', ['cliente_id'], unique=False)
    op.create_index('ix_cotizaciones_estado', 'cotizaciones', ['estado'], unique=False)
    op.create_table('cotizaciones_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cotizacion_id', sa.Integer(), nullable=False),
    sa.Column('servicio_id', sa.Integer(), nullable=True),
    sa.Column('descripcion', sa.String(length=300), nullable=False),
    sa.Column('cantidad', sa.Integer(), nullable=False),
    sa.Column('precio_unitario', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['cotizacion_id'], ['cotizaciones.id'], ),
    sa.ForeignKeyConstraint(['servicio_id'], ['servicios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('garantias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=20), nullable=False),
    sa.Column('cliente_id', sa.Integer(), nullable=False),
    sa.Column('vehiculo_id', sa.Integer(), nullable=False),
    sa.Column('orden_trabajo_id', sa.Integer(), nullable=True),
    sa.Column('factura_id', sa.Integer(), nullable=True),
    sa.Column('servicio_id', sa.Integer(), nullable=True),
    sa.Column('descripcion', sa.String(length=500), nullable=False),
    sa.Column('meses_validez', sa.Integer(), nullable=False),
    sa.Column('fecha_inicio', sa.Date(), nullable=False),
    sa.Column('fecha_fin', sa.Date(), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('nota_reclamacion', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], ),
    sa.ForeignKeyConstraint(['factura_id'], ['facturas.id'], ),
    sa.ForeignKeyConstraint(['orden_trabajo_id'], ['ordenes_trabajo.id'], ),
    sa.ForeignKeyConstraint(['servicio_id'], ['servicios.id'], ),
    sa.ForeignKeyConstraint(['vehiculo_id'], ['vehiculos.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_index('ix_garantias_cliente_id', 'garantias', ['cliente_id'], unique=False)
    op.create_index('ix_garantias_estado', 'garantias', ['estado'], unique=False)
    op.add_column('servicios', sa.Column('garantia_meses', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('servicios', 'garantia_meses')
    op.drop_index('ix_garantias_estado', table_name='garantias')
    op.drop_index('ix_garantias_cliente_id', table_name='garantias')
    op.drop_table('garantias')
    op.drop_table('cotizaciones_items')
    op.drop_index('ix_cotizaciones_estado', table_name='cotizaciones')
    op.drop_index('ix_cotizaciones_cliente_id', table_name='cotizaciones')
    op.drop_table('cotizaciones')
