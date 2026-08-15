import logging
from datetime import date, timedelta
from decimal import Decimal

from database.db import db
from models.cotizacion import Cotizacion, ESTADOS_COTIZACION
from models.cotizacion_item import CotizacionItem
from models.servicio import Servicio
from models.orden_trabajo import OrdenTrabajo

logger = logging.getLogger("siam.cotizaciones")

IVA_DEFAULT = Decimal("19.00")


class CotizacionError(Exception):
    pass


class CotizacionService:
    @staticmethod
    def _generar_numero() -> str:
        ultimo = Cotizacion.query.order_by(Cotizacion.id.desc()).first()
        if ultimo and ultimo.numero and ultimo.numero.startswith("COT-"):
            try:
                last_num = int(ultimo.numero[4:])
                return f"COT-{last_num + 1:06d}"
            except (ValueError, IndexError):
                pass
        return "COT-000001"

    @staticmethod
    def _recalcular(cotizacion: Cotizacion) -> None:
        subtotal = sum((i.subtotal or Decimal("0")) for i in cotizacion.items)
        cotizacion.subtotal = subtotal
        iva_porcentaje = cotizacion.iva_porcentaje or IVA_DEFAULT
        cotizacion.iva = (subtotal * iva_porcentaje / Decimal("100")).quantize(Decimal("0.01"))
        descuento = cotizacion.descuento or Decimal("0")
        cotizacion.total = (subtotal + cotizacion.iva - descuento).quantize(Decimal("0.01"))

    @staticmethod
    def crear(
        cliente_id: int,
        vehiculo_id: int,
        sede_id: int | None = None,
        descripcion: str | None = None,
        validez_dias: int = 15,
        iva_porcentaje: Decimal = IVA_DEFAULT,
    ) -> Cotizacion:
        cotizacion = Cotizacion(
            numero=CotizacionService._generar_numero(),
            cliente_id=cliente_id,
            vehiculo_id=vehiculo_id,
            sede_id=sede_id or None,
            estado="pendiente",
            descripcion=descripcion,
            validez_dias=validez_dias,
            iva_porcentaje=iva_porcentaje,
        )
        db.session.add(cotizacion)
        db.session.commit()
        logger.info("Cotización %s creada", cotizacion.numero)
        return cotizacion

    @staticmethod
    def agregar_item(cotizacion_id: int, servicio_id: int, cantidad: int = 1) -> CotizacionItem:
        cotizacion = db.session.get(Cotizacion, cotizacion_id)
        if not cotizacion:
            raise CotizacionError("Cotización no encontrada")
        if cotizacion.estado not in ("pendiente", "aprobada"):
            raise CotizacionError("Solo se pueden editar cotizaciones pendientes o aprobadas")
        servicio = db.session.get(Servicio, servicio_id)
        if not servicio or not servicio.activo:
            raise CotizacionError("Servicio no válido")
        cantidad = max(1, int(cantidad))
        precio = servicio.precio_estimado or Decimal("0")
        item = CotizacionItem(
            cotizacion_id=cotizacion.id,
            servicio_id=servicio.id,
            descripcion=servicio.nombre,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=(precio * cantidad).quantize(Decimal("0.01")),
        )
        db.session.add(item)
        CotizacionService._recalcular(cotizacion)
        db.session.commit()
        return item

    @staticmethod
    def agregar_item_libre(cotizacion_id: int, descripcion: str, cantidad: int, precio_unitario: Decimal) -> CotizacionItem:
        cotizacion = db.session.get(Cotizacion, cotizacion_id)
        if not cotizacion:
            raise CotizacionError("Cotización no encontrada")
        if cotizacion.estado not in ("pendiente", "aprobada"):
            raise CotizacionError("Solo se pueden editar cotizaciones pendientes o aprobadas")
        cantidad = max(1, int(cantidad))
        item = CotizacionItem(
            cotizacion_id=cotizacion.id,
            descripcion=descripcion.strip(),
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            subtotal=(precio_unitario * cantidad).quantize(Decimal("0.01")),
        )
        db.session.add(item)
        CotizacionService._recalcular(cotizacion)
        db.session.commit()
        return item

    @staticmethod
    def eliminar_item(cotizacion_id: int, item_id: int) -> bool:
        cotizacion = db.session.get(Cotizacion, cotizacion_id)
        item = db.session.get(CotizacionItem, item_id)
        if not cotizacion or not item or item.cotizacion_id != cotizacion.id:
            return False
        if cotizacion.estado not in ("pendiente", "aprobada"):
            raise CotizacionError("Solo se pueden editar cotizaciones pendientes o aprobadas")
        db.session.delete(item)
        CotizacionService._recalcular(cotizacion)
        db.session.commit()
        return True

    @staticmethod
    def cambiar_estado(cotizacion_id: int, estado: str) -> Cotizacion:
        if estado not in ESTADOS_COTIZACION:
            raise CotizacionError("Estado no válido")
        cotizacion = db.session.get(Cotizacion, cotizacion_id)
        if not cotizacion:
            raise CotizacionError("Cotización no encontrada")
        if estado == "convertida" and not cotizacion.orden_trabajo_id:
            raise CotizacionError("La cotización debe vincularse a una OT para marcarla como convertida")
        cotizacion.estado = estado
        db.session.commit()
        logger.info("Cotización %s → %s", cotizacion.numero, estado)
        return cotizacion

    @staticmethod
    def convertir_a_ot(cotizacion_id: int, mecanico_id: int | None = None) -> OrdenTrabajo:
        cotizacion = db.session.get(Cotizacion, cotizacion_id)
        if not cotizacion:
            raise CotizacionError("Cotización no encontrada")
        if cotizacion.estado != "aprobada":
            raise CotizacionError("Solo se convierten cotizaciones aprobadas")
        if cotizacion.orden_trabajo_id:
            raise CotizacionError("Esta cotización ya fue convertida en una OT")
        ultimo = OrdenTrabajo.query.order_by(OrdenTrabajo.id.desc()).first()
        if ultimo and ultimo.numero and ultimo.numero.startswith("OT-"):
            try:
                numero = f"OT-{int(ultimo.numero[3:]) + 1:06d}"
            except (ValueError, IndexError):
                numero = "OT-000001"
        else:
            numero = "OT-000001"
        descripcion = cotizacion.descripcion or "Cotización aprobada"
        ot = OrdenTrabajo(
            numero=numero,
            cliente_id=cotizacion.cliente_id,
            vehiculo_id=cotizacion.vehiculo_id,
            mecanico_id=mecanico_id or None,
            diagnostico_inicial=descripcion,
            observaciones=f"Generada desde la cotización {cotizacion.numero}",
            estado="recibido",
        )
        db.session.add(ot)
        db.session.flush()
        for item in cotizacion.items:
            if item.es_servicio:
                from models.orden_trabajo_item import OrdenTrabajoItem
                db.session.add(OrdenTrabajoItem(
                    orden_trabajo_id=ot.id,
                    descripcion=item.descripcion,
                    tiempo_minutos=0,
                    posicion=item.id,
                    completado=False,
                ))
        cotizacion.orden_trabajo_id = ot.id
        cotizacion.estado = "convertida"
        db.session.commit()
        logger.info("Cotización %s → OT %s", cotizacion.numero, ot.numero)
        return ot

    @staticmethod
    def get_para_cliente(cliente_id: int) -> list[Cotizacion]:
        return (
            Cotizacion.query.filter_by(cliente_id=cliente_id)
            .order_by(Cotizacion.created_at.desc())
            .all()
        )

    @staticmethod
    def get_para_vehiculo(vehiculo_id: int) -> list[Cotizacion]:
        return (
            Cotizacion.query.filter_by(vehiculo_id=vehiculo_id)
            .order_by(Cotizacion.created_at.desc())
            .all()
        )

    @staticmethod
    def marcar_vencidas() -> int:
        """Marca como vencidas las pendientes cuya validez ya expiró."""
        contador = 0
        pendientes = Cotizacion.query.filter_by(estado="pendiente").all()
        hoy = date.today()
        for c in pendientes:
            limite = (c.created_at.date() + timedelta(days=c.validez_dias)) if c.created_at else hoy
            if limite < hoy:
                c.estado = "vencida"
                contador += 1
        if contador:
            db.session.commit()
        return contador
