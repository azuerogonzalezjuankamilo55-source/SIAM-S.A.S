import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from database.db import db
from models.inventario import Inventario
from models.movimiento_inventario import MovimientoInventario
from models.recordatorio import Recordatorio

logger = logging.getLogger("siam.inventario_service")


class InventarioService:

    @staticmethod
    def registrar_movimiento(
        item: Inventario,
        tipo: str,
        cantidad: int,
        usuario_id: int,
        motivo: str | None = None,
        referencia: str | None = None,
        costo_unitario: Decimal | None = None,
    ) -> MovimientoInventario:
        if tipo not in ("entrada", "salida", "ajuste", "baja"):
            raise ValueError("Tipo de movimiento inválido")
        if tipo in ("entrada", "salida") and cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")
        if tipo == "baja":
            cantidad = 0
        if tipo == "entrada" and costo_unitario is not None:
            InventarioService._actualizar_costo_promedio(item, cantidad, costo_unitario)
        movimiento = item.registrar_movimiento(
            tipo=tipo, cantidad=cantidad, usuario_id=usuario_id, motivo=motivo, referencia=referencia
        )
        return movimiento

    @staticmethod
    def _actualizar_costo_promedio(item: Inventario, cantidad: int, costo_unitario: Decimal) -> None:
        costo = Decimal(costo_unitario)
        actual_cant = item.cantidad
        actual_costo = item.costo_promedio if item.costo_promedio is not None else item.precio_compra
        if actual_cant <= 0:
            item.costo_promedio = costo
            return
        total = (Decimal(actual_cant) * (actual_costo or Decimal("0")) + Decimal(cantidad) * costo)
        item.costo_promedio = (total / Decimal(actual_cant + cantidad)).quantize(Decimal("0.01"))

    @staticmethod
    def dar_baja(item: Inventario, motivo: str, usuario_id: int) -> None:
        if item.es_baja:
            raise ValueError("El producto ya está dado de baja")
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValueError("Debes indicar el motivo de la baja")
        InventarioService.registrar_movimiento(
            item, tipo="baja", cantidad=0, usuario_id=usuario_id,
            motivo=f"Baja de producto: {motivo}",
        )
        item.activo = False
        item.fecha_baja = datetime.now()
        item.motivo_baja = motivo
        item.usuario_baja_id = usuario_id
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error al dar de baja %s: %s", item.nombre, str(e), exc_info=True)
            raise RuntimeError("No se pudo dar de baja el producto.") from e
        logger.info("Producto dado de baja: %s (%s)", item.nombre, motivo)

    @staticmethod
    def restaurar(item: Inventario, usuario_id: int) -> None:
        if not item.es_baja:
            raise ValueError("El producto no está dado de baja")
        item.activo = True
        item.fecha_baja = None
        item.motivo_baja = None
        item.usuario_baja_id = None
        InventarioService.registrar_movimiento(
            item, tipo="ajuste", cantidad=item.cantidad, usuario_id=usuario_id,
            motivo="Restauración de producto dado de baja",
        )
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error al restaurar %s: %s", item.nombre, str(e), exc_info=True)
            raise RuntimeError("No se pudo restaurar el producto.") from e
        logger.info("Producto restaurado: %s", item.nombre)

    @staticmethod
    def valorizacion() -> dict:
        activos = Inventario.query.filter_by(activo=True).all()
        total_valor = Decimal("0")
        items_bajo = 0
        items_sin_stock = 0
        por_categoria: dict[str, Decimal] = {}
        for item in activos:
            costo = item.costo_promedio if item.costo_promedio is not None else item.precio_compra
            if costo is not None:
                total_valor += Decimal(item.cantidad) * Decimal(costo)
            if item.stock_bajo:
                items_bajo += 1
            if item.cantidad <= 0:
                items_sin_stock += 1
            nombre_cat = item.categoria_nombre or "Sin categoría"
            if costo is not None:
                por_categoria[nombre_cat] = por_categoria.get(nombre_cat, Decimal("0")) + (
                    Decimal(item.cantidad) * Decimal(costo)
                )
        return {
            "total_productos": len(activos),
            "total_valor": float(total_valor),
            "items_bajo": items_bajo,
            "items_sin_stock": items_sin_stock,
            "por_categoria": sorted(
                ({"categoria": k, "valor": float(v)} for k, v in por_categoria.items()),
                key=lambda x: x["valor"], reverse=True,
            ),
        }

    @staticmethod
    def get_kardex(
        inventario_id: int | None = None,
        tipo: str | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        limite: int = 200,
    ) -> list[MovimientoInventario]:
        query = MovimientoInventario.query
        if inventario_id:
            query = query.filter(MovimientoInventario.inventario_id == inventario_id)
        if tipo:
            query = query.filter(MovimientoInventario.tipo == tipo)
        if fecha_desde:
            query = query.filter(MovimientoInventario.created_at >= fecha_desde)
        if fecha_hasta:
            query = query.filter(MovimientoInventario.created_at <= fecha_hasta + timedelta(days=1))
        return query.order_by(MovimientoInventario.created_at.desc()).limit(limite).all()

    @staticmethod
    def generar_alertas_reposicion(fecha_programada: date | None = None) -> int:
        fecha_programada = fecha_programada or date.today() + timedelta(days=1)
        creados = 0
        items = Inventario.query.filter(
            Inventario.activo.is_(True),
            Inventario.cantidad <= Inventario.stock_minimo,
        ).order_by(Inventario.cantidad.asc()).all()
        for item in items:
            ya_existe = Recordatorio.query.filter(
                Recordatorio.tipo == "reposicion",
                Recordatorio.descripcion.like(f"%#{item.id}#%"),
                Recordatorio.estado.in_(["pendiente", "enviado"]),
            ).first()
            if ya_existe:
                continue
            db.session.add(Recordatorio(
                vehiculo_id=None,
                tipo="reposicion",
                titulo=f"Reponer: {item.nombre}",
                descripcion=f"#{item.id}# Stock actual {item.cantidad}, mínimo {item.stock_minimo}.",
                fecha_programada=fecha_programada,
                estado="pendiente",
                canal="portal",
            ))
            creados += 1
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Error generando alertas de reposición: %s", str(e), exc_info=True)
            raise RuntimeError("No se pudieron generar las alertas de reposición.") from e
        logger.info("Alertas de reposición generadas: %d", creados)
        return creados
