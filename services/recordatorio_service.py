import logging
from datetime import date, datetime, timedelta

from database.db import db
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.recordatorio import (
    Recordatorio,
    TIPOS_MANTENIMIENTO_LABELS,
)
from services.inteligencia_service import InteligenciaService

logger = logging.getLogger("siam.recordatorio_service")


class RecordatorioService:

    @staticmethod
    def _mapa_mantenimientos(vehiculo_id: int) -> dict[str, dict]:
        """Devuelve {clave_mantenimiento: {"nombre", "detalle", "estado"}} usando la
        recomendación del InteligenciaService."""
        datos = InteligenciaService.recomendar_mantenimiento(vehiculo_id)
        mapa: dict[str, dict] = {}
        if not datos.get("vehiculo"):
            return mapa
        for rec in datos.get("recomendaciones", []):
            clave = None
            for k, nombre in TIPOS_MANTENIMIENTO_LABELS.items():
                if rec["nombre"].startswith(nombre.split(" ")[0]):
                    clave = k
                    break
            if clave:
                mapa[clave] = rec
        return mapa

    @staticmethod
    def _url_portal_recordatorios() -> str | None:
        try:
            from flask import url_for, has_request_context
            if has_request_context():
                return url_for("portal.recordatorios")
        except Exception:
            pass
        return None

    @staticmethod
    def _notificar_cliente(vehiculo, tipo: str, titulo: str, mensaje: str) -> None:
        if not vehiculo or not vehiculo.cliente_id:
            return
        try:
            from services.notification_service import NotificationService
            NotificationService.notify_cliente(
                vehiculo.cliente_id, tipo, titulo, mensaje,
                url=RecordatorioService._url_portal_recordatorios(),
            )
        except Exception as e:
            logger.warning("No se pudo notificar recordatorio al cliente: %s", e)

    @staticmethod
    def _dias_anticipacion() -> int:
        """Días de antelación para la fecha programada desde la configuración central."""
        try:
            from models.configuracion_taller import ConfiguracionTaller
            dias = ConfiguracionTaller.get_config().notif_recordatorio_dias
            return int(dias) if dias and int(dias) > 0 else 3
        except Exception:
            return 3

    @staticmethod
    def generar_mantenimientos(fecha_programada: date | None = None) -> int:
        """Genera recordatorios pendientes para mantenimientos vencidos o por vencer.
        No duplica los que ya existen en estado pendiente/enviado."""
        fecha_programada = fecha_programada or date.today() + timedelta(
            days=RecordatorioService._dias_anticipacion()
        )
        creados: list[Recordatorio] = []
        for vehiculo in Vehiculo.query.order_by(Vehiculo.placa).all():
            mapa = RecordatorioService._mapa_mantenimientos(vehiculo.id)
            for clave, info in mapa.items():
                if info["estado"] not in ("vencido", "pendiente"):
                    continue
                ya_existe = Recordatorio.query.filter(
                    Recordatorio.vehiculo_id == vehiculo.id,
                    Recordatorio.servicio_mantenimiento == clave,
                    Recordatorio.tipo == "mantenimiento",
                    Recordatorio.estado.in_(["pendiente", "enviado"]),
                ).first()
                if ya_existe:
                    continue
                rec = Recordatorio(
                    vehiculo_id=vehiculo.id,
                    tipo="mantenimiento",
                    servicio_mantenimiento=clave,
                    titulo=info["nombre"],
                    descripcion=info["detalle"],
                    fecha_programada=fecha_programada,
                    estado="pendiente",
                    canal="portal",
                )
                db.session.add(rec)
                creados.append(rec)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error generando recordatorios: %s", str(e), exc_info=True)
            raise RuntimeError("No se pudieron generar los recordatorios.") from e
        for r in creados:
            RecordatorioService._notificar_cliente(
                r.vehiculo, "recordatorio",
                "Recordatorio de mantenimiento",
                f"Te recordamos: {r.titulo} para el {r.fecha_programada.strftime('%d/%m/%Y')}.",
            )
        logger.info("Recordatorios de mantenimiento generados: %d", len(creados))
        return len(creados)

    @staticmethod
    def crear_manual(vehiculo_id: int, titulo: str, descripcion: str | None,
                     fecha_programada: date, canal: str = "portal") -> Recordatorio:
        vehiculo = db.session.get(Vehiculo, vehiculo_id)
        if not vehiculo:
            raise ValueError("Vehículo no encontrado")
        recordatorio = Recordatorio(
            vehiculo_id=vehiculo.id,
            tipo="manual",
            titulo=titulo.strip(),
            descripcion=(descripcion or "").strip() or None,
            fecha_programada=fecha_programada,
            estado="pendiente",
            canal=canal,
        )
        db.session.add(recordatorio)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise RuntimeError("No se pudo crear el recordatorio.") from e
        RecordatorioService._notificar_cliente(
            vehiculo, "recordatorio",
            "Nuevo recordatorio",
            f"{recordatorio.titulo} — programado para el {recordatorio.fecha_programada.strftime('%d/%m/%Y')}.",
        )
        return recordatorio

    @staticmethod
    def cambiar_estado(recordatorio_id: int, nuevo_estado: str) -> Recordatorio | None:
        if nuevo_estado not in ("pendiente", "enviado", "completado", "cancelado"):
            raise ValueError("Estado inválido")
        recordatorio = db.session.get(Recordatorio, recordatorio_id)
        if not recordatorio:
            return None
        recordatorio.estado = nuevo_estado
        recordatorio.enviado_at = datetime.now() if nuevo_estado == "enviado" else None
        recordatorio.completado_at = datetime.now() if nuevo_estado == "completado" else None
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise RuntimeError("No se pudo actualizar el recordatorio.") from e
        return recordatorio

    @staticmethod
    def get_todos(estado: str | None = None, tipo: str | None = None) -> list[Recordatorio]:
        query = Recordatorio.query
        if estado:
            query = query.filter(Recordatorio.estado == estado)
        if tipo:
            query = query.filter(Recordatorio.tipo == tipo)
        return (
            query
            .outerjoin(Vehiculo)
            .order_by(Recordatorio.estado.asc(),
                      Recordatorio.fecha_programada.asc(),
                      Recordatorio.created_at.desc())
            .all()
        )

    @staticmethod
    def get_para_cliente(cliente: Cliente) -> list[Recordatorio]:
        vehiculos_ids = [v.id for v in Vehiculo.query.filter_by(cliente_id=cliente.id).all()]
        if not vehiculos_ids:
            return []
        return (
            Recordatorio.query
            .filter(
                Recordatorio.vehiculo_id.in_(vehiculos_ids),
                Recordatorio.estado.in_(["pendiente", "enviado"]),
            )
            .order_by(Recordatorio.fecha_programada.asc())
            .all()
        )
