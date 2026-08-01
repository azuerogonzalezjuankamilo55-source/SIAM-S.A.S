import logging
from typing import Any

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from services.dashboard_service import DashboardService

logger = logging.getLogger("siam.routes.dashboard")
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index() -> Any:
    data = DashboardService.get_data()
    logger.debug("Dashboard cargado: %d clientes", data.total_clientes)
    return render_template("dashboard/index.html", data=data)


@dashboard_bp.route("/api/stats")
@login_required
def api_stats() -> Any:
    data = DashboardService.get_data()
    return jsonify({
        "total_clientes": data.total_clientes,
        "total_vehiculos": data.total_vehiculos,
        "total_mecanicos": data.total_mecanicos,
        "citas_hoy": data.citas_hoy,
        "citas_pendientes": data.citas_pendientes,
        "ordenes_activas": data.ordenes_activas,
        "ordenes_listas": data.ordenes_listas,
        "facturas_pendientes": data.facturas_pendientes,
        "facturas_hoy": data.facturas_hoy,
        "inventario_bajo": data.inventario_bajo,
        "ingresos_hoy": data.ingresos_hoy,
        "ingresos_mes": data.ingresos_mes,
        "por_cobrar": data.por_cobrar,
        "ticket_promedio": data.ticket_promedio,
        "ot_retrasadas": data.ot_retrasadas_count,
        "tasa_completacion_citas": round(data.tasa_completacion_citas, 1),
    })
