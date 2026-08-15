"""initial models

Revision ID: 001
Revises:
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


TABLES = [
    "facturas_detalle",
    "facturas",
    "citas",
    "vehiculos",
    "clientes",
    "servicios",
    "mecanicos",
    "inventario",
    "usuarios",
]


def upgrade():
    _drop_if_exists()
    _create_all()


def _drop_syntax() -> str:
    bind = op.get_bind()
    return "CASCADE" if bind.dialect.name != "sqlite" else ""


def downgrade():
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} {_drop_syntax()}".strip())


def _drop_if_exists():
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} {_drop_syntax()}".strip())


def _create_all():
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("correo", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False, server_default="admin"),
        sa.Column("activo", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correo"),
    )
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("telefono", sa.String(20)),
        sa.Column("correo", sa.String(120)),
        sa.Column("direccion", sa.Text()),
        sa.Column("cedula", sa.String(20)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cedula"),
    )
    op.create_table(
        "vehiculos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("marca", sa.String(50), nullable=False),
        sa.Column("modelo", sa.String(50), nullable=False),
        sa.Column("anio", sa.Integer()),
        sa.Column("placa", sa.String(20), nullable=False),
        sa.Column("vin", sa.String(17)),
        sa.Column("color", sa.String(30)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("placa"),
        sa.UniqueConstraint("vin"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "servicios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("precio_estimado", sa.Numeric(10, 2)),
        sa.Column("duracion_estimada", sa.Integer()),
        sa.Column("categoria", sa.String(50)),
        sa.Column("activo", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mecanicos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("telefono", sa.String(20)),
        sa.Column("correo", sa.String(120)),
        sa.Column("especialidad", sa.String(100)),
        sa.Column("activo", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "citas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), nullable=False),
        sa.Column("mecanico_id", sa.Integer()),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hora", sa.Time(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("descripcion", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mecanico_id"], ["mecanicos.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "facturas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cita_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("iva", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("descuento", sa.Numeric(10, 2), server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("metodo_pago", sa.String(30)),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero"),
        sa.ForeignKeyConstraint(["cita_id"], ["citas.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "facturas_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=False),
        sa.Column("servicio_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("precio_unitario", sa.Numeric(10, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["factura_id"], ["facturas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["servicio_id"], ["servicios.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "inventario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("precio_compra", sa.Numeric(10, 2)),
        sa.Column("precio_venta", sa.Numeric(10, 2)),
        sa.Column("proveedor", sa.String(100)),
        sa.Column("categoria", sa.String(50)),
        sa.Column("stock_minimo", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
