import logging
from typing import Any

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from services.dashboard_service import DashboardService
from decorators import staff_blueprint_guard

logger = logging.getLogger("siam.routes.dashboard")
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
dashboard_bp.before_request(staff_blueprint_guard)


@dashboard_bp.route("/api/resumen")
@login_required
def api_resumen() -> Any:
    data = DashboardService.get_data()
    return jsonify({
        "ingresos_hoy": round(data.ingresos_hoy, 0),
        "ingresos_mes": round(data.ingresos_mes, 0),
        "por_cobrar": round(data.por_cobrar, 0),
        "ticket_promedio": round(data.ticket_promedio, 0),
        "citas_hoy": data.citas_hoy,
        "citas_pendientes": data.citas_pendientes,
        "ordenes_activas": data.ordenes_activas,
        "inventario_bajo": data.inventario_bajo,
        "ot_retrasadas_count": data.ot_retrasadas_count,
        "facturas_pendientes": data.facturas_pendientes,
        "facturas_hoy": data.facturas_hoy,
        "clientes_nuevos_mes": data.clientes_nuevos_mes,
        "tasa_completacion_citas": round(data.tasa_completacion_citas, 1),
        "total_clientes": data.total_clientes,
        "total_vehiculos": data.total_vehiculos,
        "total_servicios": data.total_servicios,
        "total_facturas": data.total_facturas,
        "total_mecanicos": data.total_mecanicos,
    })


@dashboard_bp.route("/")
@login_required
def index() -> Any:
    data = DashboardService.get_data()
    eventos = DashboardService.get_actividad(10)
    logger.debug("Dashboard cargado: %d clientes", data.total_clientes)
    return render_template("dashboard/index.html", data=data, eventos=eventos)


@dashboard_bp.route("/api/actividad")
@login_required
def api_actividad() -> Any:
    return jsonify({"eventos": DashboardService.get_actividad(10)})
