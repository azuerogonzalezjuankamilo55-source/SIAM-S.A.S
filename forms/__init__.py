from forms.auth_forms import LoginForm, RegisterForm
from forms.cliente_forms import ClienteForm
from forms.vehiculo_forms import VehiculoForm
from forms.servicio_forms import ServicioForm
from forms.mecanico_forms import MecanicoForm
from forms.cita_forms import CitaForm
from forms.factura_forms import FacturaForm, PagoForm, LogoForm
from forms.inventario_forms import InventarioForm, MovimientoInventarioForm, CategoriaInventarioForm
from forms.orden_trabajo_forms import OrdenTrabajoForm, CambiarEstadoForm
from forms.taller_forms import TallerConfigForm
from forms.portal_forms import SolicitarCitaForm, PerfilForm, CambiarPasswordForm

__all__ = [
    "LoginForm",
    "RegisterForm",
    "ClienteForm",
    "VehiculoForm",
    "ServicioForm",
    "MecanicoForm",
    "CitaForm",
    "FacturaForm",
    "PagoForm",
    "LogoForm",
    "InventarioForm",
    "MovimientoInventarioForm",
    "CategoriaInventarioForm",
    "OrdenTrabajoForm",
    "CambiarEstadoForm",
    "TallerConfigForm",
    "SolicitarCitaForm",
    "PerfilForm",
    "CambiarPasswordForm",
]
