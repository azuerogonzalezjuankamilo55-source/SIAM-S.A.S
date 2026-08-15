"""notificaciones

Revision ID: c1a9d4f2e6b8
Revises: e6f2b7a3c9d1
Create Date: 2026-08-14 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1a9d4f2e6b8'
down_revision = 'e6f2b7a3c9d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notificaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=30), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('mensaje', sa.Text(), nullable=True),
    sa.Column('url', sa.String(length=300), nullable=True),
    sa.Column('leida', sa.Boolean(), nullable=False),
    sa.Column('leida_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notificaciones_usuario', 'notificaciones', ['usuario_id'], unique=False)
    op.create_index('ix_notificaciones_leida', 'notificaciones', ['leida'], unique=False)
    op.create_index('ix_notificaciones_created_at', 'notificaciones', ['created_at'], unique=False)


def downgrade():
    op.drop_index('ix_notificaciones_created_at', table_name='notificaciones')
    op.drop_index('ix_notificaciones_leida', table_name='notificaciones')
    op.drop_index('ix_notificaciones_usuario', table_name='notificaciones')
    op.drop_table('notificaciones')
