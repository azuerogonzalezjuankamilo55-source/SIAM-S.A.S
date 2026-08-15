"""panel de configuración centralizado

Revision ID: b5d7e9a2c1f6
Revises: a8c4d2f6e1b9
Create Date: 2026-08-14 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5d7e9a2c1f6'
down_revision = 'a8c4d2f6e1b9'
branch_labels = None
depends_on = None


def upgrade():
    # --- ConfiguracionTaller: contacto, apariencia, citas, notificaciones, IA ---
    op.add_column('configuracion_taller', sa.Column('ciudad', sa.String(length=100), nullable=True))
    op.add_column('configuracion_taller', sa.Column('whatsapp', sa.String(length=30), nullable=True))
    op.add_column('configuracion_taller', sa.Column('sitio_web', sa.String(length=200), nullable=True))
    op.add_column('configuracion_taller', sa.Column('facebook', sa.String(length=200), nullable=True))
    op.add_column('configuracion_taller', sa.Column('instagram', sa.String(length=200), nullable=True))
    op.add_column('configuracion_taller', sa.Column('twitter', sa.String(length=200), nullable=True))
    op.add_column('configuracion_taller', sa.Column('linkedin', sa.String(length=200), nullable=True))
    op.add_column('configuracion_taller', sa.Column('color_primario', sa.String(length=7), nullable=True))
    op.add_column('configuracion_taller', sa.Column('color_primario_fuerte', sa.String(length=7), nullable=True))
    op.add_column('configuracion_taller', sa.Column('color_primario_soft', sa.String(length=7), nullable=True))
    op.add_column('configuracion_taller', sa.Column('color_acento', sa.String(length=7), nullable=True))
    op.add_column('configuracion_taller', sa.Column('citas_intervalo_min', sa.Integer(), nullable=False, server_default='30'))
    op.add_column('configuracion_taller', sa.Column('citas_min_anticipacion_horas', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('configuracion_taller', sa.Column('citas_cancelar_limite_horas', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('configuracion_taller', sa.Column('notif_email', sa.Boolean(), nullable=False, server_default=sa.text('1')))
    op.add_column('configuracion_taller', sa.Column('notif_sms', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('configuracion_taller', sa.Column('notif_whatsapp', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('configuracion_taller', sa.Column('notif_recordatorio_dias', sa.Integer(), nullable=False, server_default='7'))
    op.add_column('configuracion_taller', sa.Column('ia_activado', sa.Boolean(), nullable=False, server_default=sa.text('1')))
    op.add_column('configuracion_taller', sa.Column('ia_nombre', sa.String(length=100), nullable=True))
    op.add_column('configuracion_taller', sa.Column('ia_tono', sa.String(length=50), nullable=True))
    op.add_column('configuracion_taller', sa.Column('ia_mensaje_bienvenida', sa.Text(), nullable=True))
    op.add_column('configuracion_taller', sa.Column('ia_preguntas_sugeridas', sa.Text(), nullable=True))
    op.add_column('configuracion_taller', sa.Column('ia_contacto', sa.String(length=200), nullable=True))
    op.add_column('configuracion_taller', sa.Column('ia_mensaje_emergencia', sa.Text(), nullable=True))
    # --- Usuario: último acceso ---
    op.add_column('usuarios', sa.Column('last_access_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('usuarios', 'last_access_at')
    op.drop_column('configuracion_taller', 'ia_mensaje_emergencia')
    op.drop_column('configuracion_taller', 'ia_contacto')
    op.drop_column('configuracion_taller', 'ia_preguntas_sugeridas')
    op.drop_column('configuracion_taller', 'ia_mensaje_bienvenida')
    op.drop_column('configuracion_taller', 'ia_tono')
    op.drop_column('configuracion_taller', 'ia_nombre')
    op.drop_column('configuracion_taller', 'ia_activado')
    op.drop_column('configuracion_taller', 'notif_recordatorio_dias')
    op.drop_column('configuracion_taller', 'notif_whatsapp')
    op.drop_column('configuracion_taller', 'notif_sms')
    op.drop_column('configuracion_taller', 'notif_email')
    op.drop_column('configuracion_taller', 'citas_cancelar_limite_horas')
    op.drop_column('configuracion_taller', 'citas_min_anticipacion_horas')
    op.drop_column('configuracion_taller', 'citas_intervalo_min')
    op.drop_column('configuracion_taller', 'color_acento')
    op.drop_column('configuracion_taller', 'color_primario_soft')
    op.drop_column('configuracion_taller', 'color_primario_fuerte')
    op.drop_column('configuracion_taller', 'color_primario')
    op.drop_column('configuracion_taller', 'linkedin')
    op.drop_column('configuracion_taller', 'twitter')
    op.drop_column('configuracion_taller', 'instagram')
    op.drop_column('configuracion_taller', 'facebook')
    op.drop_column('configuracion_taller', 'sitio_web')
    op.drop_column('configuracion_taller', 'whatsapp')
    op.drop_column('configuracion_taller', 'ciudad')
