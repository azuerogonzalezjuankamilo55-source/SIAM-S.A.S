import logging
from dataclasses import dataclass
from decimal import Decimal

from database.db import db
from models.cita import Cita
from models.factura import Factura, FacturaDetalle
from models.servicio import Servicio
from models.orden_trabajo import OrdenTrabajo
from models.configuracion_taller import ConfiguracionTaller
from models.pago_factura import PagoFactura
from exceptions import BusinessRuleException, NotFoundException

logger = logging.getLogger("siam.factura_service")


@dataclass
class FacturaInput:
    cita_id: int
    servicio_ids: list[int]
    precios: list[Decimal]
    cantidades: list[int]
    descuento: Decimal
    metodo_pago: str
    notas: str = ""
    orden_trabajo_id: int | None = None


class FacturaService:

    @staticmethod
    def get_iva_rate() -> Decimal:
        config = ConfiguracionTaller.get_config()
        return config.iva_rate

    @staticmethod
    def generar(input_data: FacturaInput) -> Factura:
        logger.info("Generando factura para cita %s", input_data.cita_id)

        cita = db.session.get(Cita, input_data.cita_id)
        if cita is None:
            raise NotFoundException(f"Cita {input_data.cita_id} no encontrada")
        if cita.factura:
            raise BusinessRuleException("La cita ya tiene una factura asociada")

        if not input_data.servicio_ids:
            raise BusinessRuleException("Debe incluir al menos un servicio")

        if len(input_data.servicio_ids) != len(input_data.precios) or len(input_data.servicio_ids) != len(input_data.cantidades):
            raise BusinessRuleException("Los datos de servicios son inconsistentes")

        config = ConfiguracionTaller.get_config()
        iva_rate = config.iva_rate

        subtotal = Decimal("0")
        detalles: list[FacturaDetalle] = []

        for sid, precio, cant in zip(
            input_data.servicio_ids,
            input_data.precios,
            input_data.cantidades,
        ):
            servicio = db.session.get(Servicio, sid)
            if not servicio:
                raise NotFoundException(f"Servicio {sid} no encontrado")

            st = precio * Decimal(str(cant))
            subtotal += st
            detalles.append(FacturaDetalle(
                servicio_id=sid,
                cantidad=cant,
                precio_unitario=precio,
                subtotal=st,
            ))

        iva = (subtotal * iva_rate).quantize(Decimal("0.01"))
        descuento = input_data.descuento.quantize(Decimal("0.01"))
        total = (subtotal + iva - descuento).quantize(Decimal("0.01"))

        ultima = Factura.query.order_by(Factura.id.desc()).first()
        prefijo = config.prefijo_factura
        numero = f"{prefijo}-{(ultima.id + 1) if ultima else 1:06d}"

        factura = Factura(
            cita_id=input_data.cita_id,
            orden_trabajo_id=input_data.orden_trabajo_id,
            numero=numero,
            subtotal=subtotal,
            iva_porcentaje=config.iva_porcentaje,
            iva=iva,
            descuento=descuento,
            total=total,
            metodo_pago=input_data.metodo_pago,
            notas=input_data.notas or None,
            estado="pendiente",
            detalles=detalles,
        )

        db.session.add(factura)
        cita.estado = "completado"
        db.session.commit()

        logger.info("Factura %s generada: total=%s", numero, total)
        return factura

    @staticmethod
    def registrar_pago(factura_id: int, monto: Decimal, metodo_pago: str,
                       usuario_id: int, referencia: str = "", notas: str = "") -> PagoFactura:
        factura = db.session.get(Factura, factura_id)
        if not factura:
            raise NotFoundException(f"Factura {factura_id} no encontrada")
        if factura.estado == "anulado":
            raise BusinessRuleException("No se puede pagar una factura anulada")

        pago = PagoFactura(
            factura_id=factura_id,
            monto=monto,
            metodo_pago=metodo_pago,
            referencia=referencia or None,
            usuario_id=usuario_id,
            notas=notas or None,
            estado="confirmado",
        )
        db.session.add(pago)

        nuevo_pagado = factura.monto_pagado + monto
        if nuevo_pagado >= factura.total:
            factura.estado = "pagado"
        else:
            factura.estado = "parcial"

        db.session.commit()
        logger.info("Pago registrado: factura=%s monto=%s metodo=%s", factura.numero, monto, metodo_pago)
        return pago

    @staticmethod
    def get_orden_trabajo_servicios(orden_trabajo_id: int) -> list:
        """Obtener servicios sugeridos para una OT (diagnóstico como servicios)."""
        ot = db.session.get(OrdenTrabajo, orden_trabajo_id)
        if not ot:
            raise NotFoundException(f"OT {orden_trabajo_id} no encontrada")
        servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()
        return servicios
