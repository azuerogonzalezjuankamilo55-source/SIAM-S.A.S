"""04_facturacion_profesional: config taller, pagos, campos factura, OT

Revision ID: 004
Revises: 003
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Create configuracion_taller table
    op.create_table(
        "configuracion_taller",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_taller", sa.String(length=200), nullable=False, server_default=sa.text("'Mi Taller'")),
        sa.Column("nit", sa.String(length=30), nullable=True),
        sa.Column("direccion", sa.String(length=300), nullable=True),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("logo_path", sa.String(length=300), nullable=True),
        sa.Column("regimen", sa.String(length=50), nullable=True, server_default=sa.text("'Común'")),
        sa.Column("prefijo_factura", sa.String(length=10), nullable=True, server_default=sa.text("'FAC'")),
        sa.Column("resolucion_dian", sa.String(length=50), nullable=True),
        sa.Column("iva_porcentaje", sa.Numeric(4, 2), nullable=False, server_default=sa.text("19.00")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert default config
    op.execute(
        "INSERT INTO configuracion_taller (nombre_taller) VALUES ('Mi Taller')"
    )

    # 2. Create pagos_factura table
    op.create_table(
        "pagos_factura",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=False),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("metodo_pago", sa.String(length=30), nullable=False),
        sa.Column("referencia", sa.String(length=100), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default=sa.text("'confirmado'")),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["factura_id"], ["facturas.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pagos_factura_factura_id"), "pagos_factura", ["factura_id"])

    # 3. Add columns to facturas
    op.add_column("facturas", sa.Column("orden_trabajo_id", sa.Integer(), nullable=True))
    op.add_column("facturas", sa.Column("iva_porcentaje", sa.Numeric(4, 2), nullable=True, server_default=sa.text("19.00")))
    op.add_column("facturas", sa.Column("notas", sa.Text(), nullable=True))
    op.add_column("facturas", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_facturas_ot", "facturas", "ordenes_trabajo", ["orden_trabajo_id"], ["id"])

    # Update existing facturas with iva_porcentaje from their old iva calculation
    op.execute("UPDATE facturas SET iva_porcentaje = 19.00 WHERE iva_porcentaje IS NULL")

    op.alter_column("facturas", "iva_porcentaje", nullable=False, server_default=sa.text("19.00"))

    # 4. Add descuento column to facturas_detalle
    op.add_column("facturas_detalle", sa.Column("descuento", sa.Numeric(10, 2), nullable=True, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("facturas_detalle", "descuento")
    op.drop_constraint("fk_facturas_ot", "facturas", type_="foreignkey")
    op.drop_column("facturas", "updated_at")
    op.drop_column("facturas", "notas")
    op.drop_column("facturas", "iva_porcentaje")
    op.drop_column("facturas", "orden_trabajo_id")
    op.drop_index(op.f("ix_pagos_factura_factura_id"), table_name="pagos_factura")
    op.drop_table("pagos_factura")
    op.drop_table("configuracion_taller")
