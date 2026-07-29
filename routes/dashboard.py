import logging
from typing import Any

from flask import Blueprint, render_template
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
