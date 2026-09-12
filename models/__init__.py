from models.usuario import Usuario
from models.cliente import Cliente
from models.vehiculo import Vehiculo
from models.servicio import Servicio
from models.mecanico import Mecanico
from models.cita import Cita
from models.factura import Factura, FacturaDetalle
from models.inventario import Inventario
from models.orden_trabajo import OrdenTrabajo
from models.orden_trabajo_historial import OrdenTrabajoHistorial
from models.orden_trabajo_item import OrdenTrabajoItem
from models.orden_trabajo_foto import OrdenTrabajoFoto
from models.orden_trabajo_repuesto import OrdenTrabajoRepuesto
from models.categoria_inventario import CategoriaInventario
from models.movimiento_inventario import MovimientoInventario
from models.configuracion_taller import ConfiguracionTaller
from models.pago_factura import PagoFactura
from models.asistencia import AsistenciaEmergencia
from models.historial_vehiculo import HistorialVehiculo, TIPOS_HISTORIAL, TIPOS_HISTORIAL_LABELS
from models.historial_foto import HistorialFoto, TIPOS_FOTO_HISTORIAL, TIPOS_FOTO_HISTORIAL_LABELS
from models.recordatorio import (
    Recordatorio,
    TIPOS_RECORDATORIO,
    ESTADOS_RECORDATORIO,
    CANALES_RECORDATORIO,
    TIPOS_MANTENIMIENTO,
    TIPOS_MANTENIMIENTO_LABELS,
)
from models.notificacion import Notificacion, TIPOS_NOTIFICACION, TIPOS_NOTIFICACION_LABELS
from models.adjunto import Adjunto, TIPOS_ADJUNTO
from models.sede import Sede
from models.cotizacion import (
    Cotizacion, ESTADOS_COTIZACION, ESTADOS_COTIZACION_LABELS,
)
from models.cotizacion_item import CotizacionItem
from models.garantia import Garantia, ESTADOS_GARANTIA, ESTADOS_GARANTIA_LABELS
from models.ubicacion_cliente import UbicacionCliente
