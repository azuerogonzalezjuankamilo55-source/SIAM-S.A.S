import logging
from typing import Any

from database.db import db
from models import Notificacion, Usuario

logger = logging.getLogger("siam.notificaciones")


class NotificationService:
    """Crea y consulta notificaciones por usuario (cliente o staff)."""

    @staticmethod
    def notify(
        usuario_id: int,
        tipo: str,
        titulo: str,
        mensaje: str | None = None,
        url: str | None = None,
        commit: bool = True,
    ) -> Notificacion:
        n = Notificacion(
            usuario_id=usuario_id,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
        )
        db.session.add(n)
        if commit:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error("No se pudo crear notificación: %s", e)
                raise
        return n

    @staticmethod
    def notify_roles(
        roles: list[str],
        tipo: str,
        titulo: str,
        mensaje: str | None = None,
        url: str | None = None,
        commit: bool = True,
    ) -> list[Notificacion]:
        """Notifica a todos los usuarios activos con alguno de los roles."""
        usuarios = Usuario.query.filter(
            Usuario.rol.in_(roles), Usuario.activo.is_(True)
        ).all()
        creadas: list[Notificacion] = []
        for u in usuarios:
            creadas.append(
                NotificationService.notify(u.id, tipo, titulo, mensaje, url, commit=False)
            )
        if commit and creadas:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error("No se pudo crear notificaciones por rol: %s", e)
                raise
        return creadas

    @staticmethod
    def notify_cliente(
        cliente_id: int,
        tipo: str,
        titulo: str,
        mensaje: str | None = None,
        url: str | None = None,
        commit: bool = True,
    ) -> Notificacion | None:
        """Notifica al usuario del cliente si este tiene cuenta en la plataforma."""
        from models.cliente import Cliente

        cliente = db.session.get(Cliente, cliente_id)
        if cliente and cliente.usuario:
            return NotificationService.notify(
                cliente.usuario.id, tipo, titulo, mensaje, url, commit=commit
            )
        return None

    @staticmethod
    def notify_staff(
        tipo: str,
        titulo: str,
        mensaje: str | None = None,
        url: str | None = None,
        commit: bool = True,
    ) -> list[Notificacion]:
        """Notifica a todo el personal (admin, recepción y mecánicos)."""
        return NotificationService.notify_roles(
            ["admin", "recepcion", "mecanico"], tipo, titulo, mensaje, url, commit=commit
        )

    @staticmethod
    def unread_count(usuario_id: int) -> int:
        return Notificacion.query.filter_by(usuario_id=usuario_id, leida=False).count()

    @staticmethod
    def list_for(usuario_id: int, limit: int = 20) -> list[Notificacion]:
        return (
            Notificacion.query.filter_by(usuario_id=usuario_id)
            .order_by(Notificacion.created_at.desc(), Notificacion.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def list_all(
        usuario_id: int,
        tipo: str | None = None,
        solo_no_leidas: bool = False,
        limit: int = 100,
    ) -> list[Notificacion]:
        query = Notificacion.query.filter_by(usuario_id=usuario_id)
        if tipo:
            query = query.filter(Notificacion.tipo == tipo)
        if solo_no_leidas:
            query = query.filter(Notificacion.leida.is_(False))
        return (
            query.order_by(Notificacion.created_at.desc(), Notificacion.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def eliminar(usuario_id: int, notificacion_id: int) -> bool:
        """Elimina una notificación. Solo el dueño puede hacerlo (protege IDOR)."""
        n = Notificacion.query.filter_by(id=notificacion_id, usuario_id=usuario_id).first()
        if not n:
            return False
        db.session.delete(n)
        db.session.commit()
        return True

    @staticmethod
    def to_dict(n: Notificacion) -> dict[str, Any]:
        return {
            "id": n.id,
            "tipo": n.tipo,
            "tipo_label": n.tipo_label,
            "titulo": n.titulo,
            "mensaje": n.mensaje,
            "url": n.url,
            "leida": n.leida,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }

    @staticmethod
    def mark_read(usuario_id: int, notificacion_id: int) -> bool:
        """Marca como leída. Solo el dueño puede hacerlo (protege IDOR)."""
        n = Notificacion.query.filter_by(id=notificacion_id, usuario_id=usuario_id).first()
        if not n:
            return False
        if not n.leida:
            n.leida = True
            n.leida_at = db.func.now()
            db.session.commit()
        return True

    @staticmethod
    def mark_all_read(usuario_id: int) -> int:
        pendientes = Notificacion.query.filter_by(usuario_id=usuario_id, leida=False).all()
        for n in pendientes:
            n.leida = True
            n.leida_at = db.func.now()
        db.session.commit()
        return len(pendientes)
