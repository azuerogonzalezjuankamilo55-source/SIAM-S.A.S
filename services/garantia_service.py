import logging
from datetime import date, timedelta

from database.db import db
from models.garantia import Garantia, ESTADOS_GARANTIA
from models.orden_trabajo import OrdenTrabajo
from models.servicio import Servicio

logger = logging.getLogger("siam.garantias")


class GarantiaError(Exception):
    pass


class GarantiaService:
    @staticmethod
    def _generar_codigo() -> str:
        ultima = Garantia.query.order_by(Garantia.id.desc()).first()
        if ultima and ultima.codigo and ultima.codigo.startswith("GAR-"):
            try:
                last_num = int(ultima.codigo[4:])
                return f"GAR-{last_num + 1:06d}"
            except (ValueError, IndexError):
                pass
        return "GAR-000001"

    @staticmethod
    def _fecha_fin(meses: int, base: date | None = None) -> date:
        return (base or date.today()) + timedelta(days=30 * max(1, meses))

    @staticmethod
    def crear(
        cliente_id: int,
        vehiculo_id: int,
        descripcion: str,
        meses_validez: int = 3,
        orden_trabajo_id: int | None = None,
        servicio_id: int | None = None,
    ) -> Garantia:
        if meses_validez <= 0:
            raise GarantiaError("Los meses de validez deben ser positivos")
        garantia = Garantia(
            codigo=GarantiaService._generar_codigo(),
            cliente_id=cliente_id,
            vehiculo_id=vehiculo_id,
            orden_trabajo_id=orden_trabajo_id or None,
            servicio_id=servicio_id or None,
            descripcion=descripcion.strip(),
            meses_validez=meses_validez,
            fecha_inicio=date.today(),
            fecha_fin=GarantiaService._fecha_fin(meses_validez),
            estado="activa",
        )
        db.session.add(garantia)
        db.session.commit()
        logger.info("Garantía %s creada (%s meses)", garantia.codigo, meses_validez)
        return garantia

    @staticmethod
    def crear_para_ot(orden_trabajo_id: int, meses_validez: int = 3) -> Garantia | None:
        ot = db.session.get(OrdenTrabajo, orden_trabajo_id)
        if not ot:
            raise GarantiaError("OT no encontrada")
        if ot.estado != "entregado":
            raise GarantiaError("La OT debe estar entregada para generar su garantía")
        if Garantia.query.filter_by(orden_trabajo_id=ot.id).first():
            raise GarantiaError("Esta OT ya tiene una garantía registrada")
        descripcion = f"Garantía del servicio realizado en la OT {ot.numero}"
        return GarantiaService.crear(
            cliente_id=ot.cliente_id,
            vehiculo_id=ot.vehiculo_id,
            descripcion=descripcion,
            meses_validez=meses_validez,
            orden_trabajo_id=ot.id,
            servicio_id=None,
        )

    @staticmethod
    def crear_desde_servicio(
        orden_trabajo_id: int, servicio_id: int, meses_validez: int | None = None
    ) -> Garantia | None:
        ot = db.session.get(OrdenTrabajo, orden_trabajo_id)
        servicio = db.session.get(Servicio, servicio_id)
        if not ot:
            raise GarantiaError("OT no encontrada")
        if not servicio or not servicio.garantia_meses:
            return None
        if ot.estado != "entregado":
            raise GarantiaError("La OT debe estar entregada para generar su garantía")
        if Garantia.query.filter_by(orden_trabajo_id=ot.id, servicio_id=servicio.id).first():
            raise GarantiaError("Ese servicio ya tiene garantía en esta OT")
        meses = meses_validez or servicio.garantia_meses
        return GarantiaService.crear(
            cliente_id=ot.cliente_id,
            vehiculo_id=ot.vehiculo_id,
            descripcion=f"Garantía de {servicio.nombre} (OT {ot.numero})",
            meses_validez=meses,
            orden_trabajo_id=ot.id,
            servicio_id=servicio.id,
        )

    @staticmethod
    def cambiar_estado(garantia_id: int, estado: str, nota: str | None = None) -> Garantia:
        if estado not in ESTADOS_GARANTIA:
            raise GarantiaError("Estado no válido")
        garantia = db.session.get(Garantia, garantia_id)
        if not garantia:
            raise GarantiaError("Garantía no encontrada")
        garantia.estado = estado
        if nota is not None:
            garantia.nota_reclamacion = nota.strip() or None
        db.session.commit()
        logger.info("Garantía %s → %s", garantia.codigo, estado)
        return garantia

    @staticmethod
    def actualizar_estados_vencidas() -> int:
        """Marca como caducadas las activas cuya fecha de fin ya pasó."""
        contador = 0
        activas = Garantia.query.filter_by(estado="activa").all()
        hoy = date.today()
        for g in activas:
            if (g.fecha_fin or date.today()) < hoy:
                g.estado = "caducada"
                contador += 1
        if contador:
            db.session.commit()
        return contador

    @staticmethod
    def get_para_cliente(cliente_id: int) -> list[Garantia]:
        return (
            Garantia.query.filter_by(cliente_id=cliente_id)
            .order_by(Garantia.created_at.desc())
            .all()
        )

    @staticmethod
    def get_para_vehiculo(vehiculo_id: int) -> list[Garantia]:
        return (
            Garantia.query.filter_by(vehiculo_id=vehiculo_id)
            .order_by(Garantia.created_at.desc())
            .all()
        )
