"""03_mejoras_inventario: categorías, movimientos, nuevos campos

Revision ID: 003
Revises: 002
Create Date: 2026-07-28
"""
from typing import Any
from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: str = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create categorias_inventario table
    op.create_table(
        "categorias_inventario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("padre_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["padre_id"],
            ["categorias_inventario.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )

    # 2. Create movimientos_inventario table
    op.create_table(
        "movimientos_inventario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("saldo_anterior", sa.Integer(), nullable=False),
        sa.Column("saldo_posterior", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("referencia", sa.String(length=100), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["inventario_id"], ["inventario.id"],),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_movimientos_inventario_inventario_id"), "movimientos_inventario", ["inventario_id"])

    # 3. Add new columns to inventario
    op.add_column("inventario", sa.Column("sku", sa.String(length=50), nullable=True))
    op.add_column("inventario", sa.Column("codigo_barras", sa.String(length=100), nullable=True))
    op.add_column("inventario", sa.Column("ubicacion", sa.String(length=50), nullable=True))
    op.add_column("inventario", sa.Column("costo_promedio", sa.Numeric(10, 2), nullable=True))
    op.add_column("inventario", sa.Column("categoria_id", sa.Integer(), nullable=True))
    op.add_column("inventario", sa.Column("stock_critico", sa.Integer(), nullable=True, server_default=sa.text("0")))
    op.add_column("inventario", sa.Column("activo", sa.Boolean(), nullable=True, server_default=sa.text("true")))
    op.add_column("inventario", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_inventario_categoria", "inventario", "categorias_inventario",
        ["categoria_id"], ["id"],
    )
    op.create_unique_constraint("uq_inventario_sku", "inventario", ["sku"])

    # 4. Migrate existing categoria text values into categorias_inventario
    results = conn.execute(
        sa.text("SELECT DISTINCT categoria FROM inventario WHERE categoria IS NOT NULL AND categoria != ''")
    ).fetchall()
    for row in results:
        nombre = row[0]
        exists = conn.execute(
            sa.text("SELECT id FROM categorias_inventario WHERE nombre = :n"),
            {"n": nombre},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text("INSERT INTO categorias_inventario (nombre) VALUES (:n)"),
                {"n": nombre},
            )

    # Map old categoria text -> new categoria_id
    rows = conn.execute(
        sa.text("SELECT id, categoria FROM inventario WHERE categoria IS NOT NULL AND categoria != ''")
    ).fetchall()
    for row in rows:
        cat_row = conn.execute(
            sa.text("SELECT id FROM categorias_inventario WHERE nombre = :n"),
            {"n": row[1]},
        ).fetchone()
        if cat_row:
            conn.execute(
                sa.text("UPDATE inventario SET categoria_id = :cid WHERE id = :iid"),
                {"cid": cat_row[0], "iid": row[0]},
            )

    # 5. Drop old categoria column
    op.drop_column("inventario", "categoria")


def downgrade() -> None:
    op.add_column("inventario", sa.Column("categoria", sa.String(length=50), nullable=True))
    op.drop_constraint("fk_inventario_categoria", "inventario", type_="foreignkey")
    op.drop_column("inventario", "updated_at")
    op.drop_column("inventario", "activo")
    op.drop_column("inventario", "stock_critico")
    op.drop_column("inventario", "categoria_id")
    op.drop_column("inventario", "costo_promedio")
    op.drop_column("inventario", "ubicacion")
    op.drop_column("inventario", "codigo_barras")
    op.drop_column("inventario", "sku")
    op.drop_index(op.f("ix_movimientos_inventario_inventario_id"), table_name="movimientos_inventario")
    op.drop_table("movimientos_inventario")
    op.drop_table("categorias_inventario")
