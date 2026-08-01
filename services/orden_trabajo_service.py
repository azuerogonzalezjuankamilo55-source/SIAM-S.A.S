import logging
from datetime import date
from decimal import Decimal

from database.db import db
from models.orden_trabajo import OrdenTrabajo
from models.orden_trabajo_item import OrdenTrabajoItem
from models.orden_trabajo_foto import OrdenTrabajoFoto
from models.orden_trabajo_repuesto import OrdenTrabajoRepuesto
from models.inventario import Inventario
from exceptions import BusinessRuleException, NotFoundException
from services.image_service import ImageService, ImageError

logger = logging.getLogger("siam.orden_trabajo_service")

NIVELES_COMBUSTIBLE = ["Vacio", "1/4", "1/2", "3/4", "Lleno"]


class OrdenTrabajoService:

    @staticmethod
    def _get_orden(orden_trabajo_id: int) -> OrdenTrabajo:
        orden = db.session.get(OrdenTrabajo, orden_trabajo_id)
        if not orden:
            raise NotFoundException(f"OT {orden_trabajo_id} no encontrada")
        return orden

    # ---------- Checklist / tiempos ----------

    @staticmethod
    def agregar_item(orden_trabajo_id: int, descripcion: str,
                     tiempo_minutos: int | None = None) -> OrdenTrabajoItem:
        orden = OrdenTrabajoService._get_orden(orden_trabajo_id)
        if not descripcion.strip():
            raise BusinessRuleException("La descripción de la tarea es obligatoria")
        posicion = max((i.posicion for i in orden.items), default=-1) + 1
        item = OrdenTrabajoItem(
            orden_trabajo_id=orden.id,
            descripcion=descripcion.strip(),
            tiempo_minutos=tiempo_minutos,
            posicion=posicion,
        )
        db.session.add(item)
        db.session.commit()
        logger.info("Item agregado a OT %s: %s", orden.numero, descripcion)
        return item

    @staticmethod
    def toggle_item(item_id: int) -> OrdenTrabajoItem:
        item = db.session.get(OrdenTrabajoItem, item_id)
        if not item:
            raise NotFoundException("Item no encontrado")
        item.completado = not item.completado
        db.session.commit()
        return item

    @staticmethod
    def actualizar_item(item_id: int, descripcion: str,
                        tiempo_minutos: int | None = None) -> OrdenTrabajoItem:
        item = db.session.get(OrdenTrabajoItem, item_id)
        if not item:
            raise NotFoundException("Item no encontrado")
        if not descripcion.strip():
            raise BusinessRuleException("La descripción de la tarea es obligatoria")
        item.descripcion = descripcion.strip()
        item.tiempo_minutos = tiempo_minutos
        db.session.commit()
        return item

    @staticmethod
    def eliminar_item(item_id: int) -> None:
        item = db.session.get(OrdenTrabajoItem, item_id)
        if not item:
            raise NotFoundException("Item no encontrado")
        db.session.delete(item)
        db.session.commit()

    # ---------- Repuestos ----------

    @staticmethod
    def agregar_repuesto(orden_trabajo_id: int, inventario_id: int, cantidad: int,
                         precio_unitario: Decimal, nota: str | None = None,
                         usuario_id: int | None = None) -> OrdenTrabajoRepuesto:
        orden = OrdenTrabajoService._get_orden(orden_trabajo_id)
        item_inv = db.session.get(Inventario, inventario_id)
        if not item_inv:
            raise NotFoundException("Repuesto no encontrado en inventario")
        if cantidad <= 0:
            raise BusinessRuleException("La cantidad debe ser mayor a cero")
        if item_inv.cantidad < cantidad:
            raise BusinessRuleException(
                f"Stock insuficiente de '{item_inv.nombre}': disponible {item_inv.cantidad}"
            )

        repuesto = OrdenTrabajoRepuesto(
            orden_trabajo_id=orden.id,
            inventario_id=inventario_id,
            cantidad=cantidad,
            precio_unitario=precio_unitario.quantize(Decimal("0.01")),
            nota=nota or None,
        )
        db.session.add(repuesto)
        item_inv.registrar_movimiento(
            tipo="salida",
            cantidad=cantidad,
            usuario_id=usuario_id,
            motivo=f"Repuesto usado en {orden.numero}",
            referencia=orden.numero,
        )
        db.session.commit()
        logger.info("Repuesto agregado a OT %s: %s x%d", orden.numero, item_inv.nombre, cantidad)
        return repuesto

    @staticmethod
    def eliminar_repuesto(repuesto_id: int, usuario_id: int | None = None) -> None:
        repuesto = db.session.get(OrdenTrabajoRepuesto, repuesto_id)
        if not repuesto:
            raise NotFoundException("Repuesto no encontrado")
        orden = repuesto.orden_trabajo_id
        item_inv = db.session.get(Inventario, repuesto.inventario_id)
        db.session.delete(repuesto)
        if item_inv:
            item_inv.registrar_movimiento(
                tipo="entrada",
                cantidad=repuesto.cantidad,
                usuario_id=usuario_id,
                motivo="Devolución de repuesto de OT",
                referencia=f"OT-{orden}",
            )
        db.session.commit()

    # ---------- Fotos ----------

    @staticmethod
    def guardar_foto(orden_trabajo_id: int, file, descripcion: str | None = None,
                     upload_root: str | None = None) -> OrdenTrabajoFoto:
        orden = OrdenTrabajoService._get_orden(orden_trabajo_id)
        if not file or not getattr(file, "filename", ""):
            raise BusinessRuleException("Selecciona un archivo de imagen")
        try:
            ruta_publica = ImageService.guardar(file, "ot", upload_root=upload_root)
        except ImageError as e:
            raise BusinessRuleException(str(e))

        foto = OrdenTrabajoFoto(
            orden_trabajo_id=orden.id,
            path=ruta_publica,
            descripcion=descripcion or None,
        )
        db.session.add(foto)
        db.session.commit()
        logger.info("Foto agregada a OT %s: %s", orden.numero, ruta_publica)
        return foto

    @staticmethod
    def eliminar_foto(foto_id: int, upload_root: str | None = None) -> None:
        foto = db.session.get(OrdenTrabajoFoto, foto_id)
        if not foto:
            raise NotFoundException("Foto no encontrada")
        ruta_publica = foto.path
        db.session.delete(foto)
        db.session.commit()
        ImageService.eliminar(ruta_publica, upload_root=upload_root)

    # ---------- Firmas / entrega ----------

    @staticmethod
    def guardar_firma(orden_trabajo_id: int, tipo: str, file,
                      upload_root: str | None = None) -> OrdenTrabajo:
        orden = OrdenTrabajoService._get_orden(orden_trabajo_id)
        if tipo not in ("mecanico", "cliente"):
            raise BusinessRuleException("Tipo de firma inválido")
        if not file or not getattr(file, "filename", ""):
            raise BusinessRuleException("Selecciona una imagen de firma")
        try:
            ruta_publica = ImageService.guardar(file, "firmas", upload_root=upload_root)
        except ImageError as e:
            raise BusinessRuleException(str(e))

        if tipo == "mecanico":
            orden.firma_mecanico_path = ruta_publica
        else:
            orden.firma_cliente_path = ruta_publica
        db.session.commit()
        logger.info("Firma de %s guardada en OT %s", tipo, orden.numero)
        return orden

    @staticmethod
    def entregar(orden_trabajo_id: int, kms_salida: int | None = None,
                 nivel_combustible_salida: str | None = None,
                 usuario_id: int | None = None) -> OrdenTrabajo:
        orden = OrdenTrabajoService._get_orden(orden_trabajo_id)
        orden.kms_salida = kms_salida or orden.kms_salida
        if nivel_combustible_salida:
            if nivel_combustible_salida not in NIVELES_COMBUSTIBLE:
                raise BusinessRuleException("Nivel de combustible inválido")
            orden.nivel_combustible_salida = nivel_combustible_salida
        orden.estado = "entregado"
        orden.fecha_entrega = date.today()
        db.session.commit()

        try:
            from services.historial_service import HistorialService
            HistorialService.registrar_desde_orden(orden, usuario_id)
        except Exception as e:
            logger.warning("No se pudo registrar historial de OT %s: %s", orden.numero, e)
        return orden
