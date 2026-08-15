import os
import logging
from typing import Any

from flask import Flask, redirect, url_for, render_template, send_from_directory, flash
from flask_login import LoginManager
from flask_migrate import Migrate, upgrade
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import config_by_name
from database.db import db
from models import Usuario
from exceptions import SIAMException


login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    strategy="moving-window",
)


def create_app(config_name: str | None = None) -> Flask:

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)

    app_config = config_by_name.get(
        config_name,
        config_by_name["default"]
    )

    app.config.from_object(app_config)

    if hasattr(app_config, "validate"):
        app_config.validate()

    # ==========================================================
    # EXTENSIONES
    # ==========================================================

    db.init_app(app)

    migrate.init_app(app, db)

    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Por favor inicia sesión para acceder."
    login_manager.login_message_category = "warning"

    csrf.init_app(app)

    limiter.init_app(app)

    # ==========================================================
    # CONFIGURACIÓN
    # ==========================================================

    configure_logging(app)

    register_blueprints(app)

    register_error_handlers(app)

    configure_security_headers(app)

    register_seo_routes(app)

    register_template_processors(app)

    # ==========================================================
    # MIGRACIONES AUTOMÁTICAS EN RENDER
    # ==========================================================

    if (
        os.getenv("RENDER") == "true"
        or os.getenv("RENDER") == "1"
        or os.getenv("AUTO_MIGRATE") == "true"
    ):
        run_migrations(app)

    # ==========================================================
    # RUTA PRINCIPAL
    # ==========================================================

    @app.route("/")
    def index() -> Any:
        return render_template("landing.html")

    # ==========================================================
    # HEALTH CHECK
    # ==========================================================

    @app.route("/health")
    def health() -> Any:

        try:

            db.session.execute(
                db.text("SELECT 1")
            )

            db.session.commit()

            db_ok = True

        except Exception:

            db.session.rollback()

            db_ok = False

        return {
            "status": "healthy" if db_ok else "degraded",
            "app": "SIAM",
            "version": "2.0.0",
            "database": "connected" if db_ok else "unreachable",
        }, 200 if db_ok else 503

    return app


# ==============================================================
# MIGRACIONES AUTOMÁTICAS
# ==============================================================

def run_migrations(app: Flask) -> None:

    logger = app.logger

    logger.info("==========================================")
    logger.info("SIAM - MIGRACIONES AUTOMÁTICAS")
    logger.info("==========================================")

    try:

        with app.app_context():

            logger.info(
                "Comprobando migraciones de base de datos..."
            )

            upgrade()

            logger.info(
                "Migraciones ejecutadas correctamente."
            )

    except Exception as error:

        logger.exception(
            "ERROR ejecutando las migraciones: %s",
            error
        )

        # Es importante detener el arranque si la base de datos
        # no puede actualizarse.
        raise


# ==============================================================
# SECURITY HEADERS
# ==============================================================

def configure_security_headers(app: Flask) -> None:

    @app.after_request
    def add_security_headers(response):

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["X-XSS-Protection"] = "0"

        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )

        response.headers["Permissions-Policy"] = (
            "geolocation=(self), microphone=(), camera=()"
        )

        response.headers["X-Powered-By"] = "SIAM"

        if not app.debug:

            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' "
                "cdn.jsdelivr.net cdnjs.cloudflare.com unpkg.com; "
                "style-src 'self' 'unsafe-inline' "
                "cdn.jsdelivr.net unpkg.com cdnjs.cloudflare.com "
                "fonts.googleapis.com; "
                "img-src 'self' data: "
                "https://*.tile.openstreetmap.org; "
                "font-src 'self' "
                "cdn.jsdelivr.net cdnjs.cloudflare.com "
                "fonts.gstatic.com; "
                "connect-src 'self'"
            )

        return response


# ==============================================================
# LOGGING
# ==============================================================

def configure_logging(app: Flask) -> None:

    level = (
        logging.DEBUG
        if app.debug
        else logging.INFO
    )

    app.logger.setLevel(level)

    handler = logging.StreamHandler()

    handler.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)

    if app.logger.handlers:
        app.logger.handlers.clear()

    app.logger.addHandler(handler)

    app.logger.propagate = False

    logger = logging.getLogger("siam")

    logger.setLevel(level)

    logger.addHandler(handler)

    logger.propagate = False

    if not app.debug:

        file_handler = logging.FileHandler(
            "siam.log"
        )

        file_handler.setLevel(
            logging.WARNING
        )

        file_handler.setFormatter(
            formatter
        )

        logger.addHandler(
            file_handler
        )

    app.logger.info(
        "SIAM iniciado en modo %s",
        "produccion" if not app.debug else "desarrollo"
    )


# ==============================================================
# BLUEPRINTS
# ==============================================================

def register_blueprints(app: Flask) -> None:

    from routes import (
        auth_bp,
        dashboard_bp,
        clientes_bp,
        vehiculos_bp,
        servicios_bp,
        mecanicos_bp,
        citas_bp,
        facturas_bp,
        inventario_bp,
        ordenes_trabajo_bp,
        assistant_bp,
        sedes_bp,
        api_bp,
        portal_bp,
        ia_bp,
        recordatorios_bp,
        reportes_bp,
        notificaciones_bp,
        cotizaciones_bp,
        garantias_bp,
        configuracion_bp,
    )

    app.register_blueprint(auth_bp)

    app.register_blueprint(dashboard_bp)

    app.register_blueprint(clientes_bp)

    app.register_blueprint(vehiculos_bp)

    app.register_blueprint(servicios_bp)

    app.register_blueprint(mecanicos_bp)

    app.register_blueprint(citas_bp)

    app.register_blueprint(facturas_bp)

    app.register_blueprint(inventario_bp)

    app.register_blueprint(ordenes_trabajo_bp)

    app.register_blueprint(assistant_bp)

    app.register_blueprint(sedes_bp)

    app.register_blueprint(api_bp)

    app.register_blueprint(portal_bp)

    app.register_blueprint(ia_bp)

    app.register_blueprint(recordatorios_bp)

    app.register_blueprint(reportes_bp)

    app.register_blueprint(notificaciones_bp)

    app.register_blueprint(cotizaciones_bp)

    app.register_blueprint(garantias_bp)

    app.register_blueprint(configuracion_bp)


# ==============================================================
# ERROR HANDLERS
# ==============================================================

def register_error_handlers(app: Flask) -> None:

    logger = logging.getLogger(
        "siam.error"
    )

    @app.errorhandler(404)
    def not_found(_error: Any) -> Any:

        return render_template(
            "errors/404.html"
        ), 404

    @app.errorhandler(500)
    def server_error(_error: Any) -> Any:

        logger.exception(
            "Error interno del servidor"
        )

        return render_template(
            "errors/500.html"
        ), 500

    @app.errorhandler(403)
    def forbidden(_error: Any) -> Any:

        return render_template(
            "errors/403.html"
        ), 403

    @app.errorhandler(429)
    def ratelimit_error(_error: Any) -> Any:

        return render_template(
            "errors/429.html"
        ), 429

    @app.errorhandler(SIAMException)
    def handle_siam_exception(
        error: SIAMException
    ) -> Any:

        logger.warning(
            "SIAMException: %s",
            error.description
        )

        if error.status_code == 401:

            flash(
                error.description,
                "warning"
            )

            return redirect(
                url_for("auth.login")
            )

        return render_template(
            "errors/error.html",
            error=error
        ), error.status_code


# ==============================================================
# SEO
# ==============================================================

def register_seo_routes(app: Flask) -> None:

    @app.route("/robots.txt")
    def robots_txt():

        return send_from_directory(
            app.static_folder,
            "robots.txt"
        )

    @app.route("/sitemap.xml")
    def sitemap_xml():

        return send_from_directory(
            app.static_folder,
            "sitemap.xml"
        )

    @app.route("/manifest.json")
    def manifest_json():

        return send_from_directory(
            app.static_folder,
            "manifest.json"
        )

    @app.route("/favicon.ico")
    def favicon():

        return send_from_directory(
            app.static_folder,
            "favicon.ico"
        )


# ==============================================================
# TEMPLATE PROCESSORS
# ==============================================================

def register_template_processors(app: Flask) -> None:

    from services.image_service import ImageService
    from flask import g

    @app.context_processor
    def inject_globals():

        return {
            "app_name": "SIAM",
            "app_description": "Sistema Integral Automotriz",
            "app_url": os.getenv(
                "APP_URL",
                "https://siam.onrender.com"
            ),
            "current_year": __import__(
                "datetime"
            ).datetime.now().year,
        }

    @app.context_processor
    def inject_taller_config():

        config = getattr(
            g,
            "_taller_config",
            None
        )

        if config is None:

            try:

                from models.configuracion_taller import (
                    ConfiguracionTaller
                )

                config = (
                    ConfiguracionTaller.query.first()
                )

            except Exception:

                config = None

            g._taller_config = config

        return {
            "taller_config": config
        }

    @app.context_processor
    def inject_appearance():

        from services.configuracion_service import (
            ConfiguracionService
        )

        config = getattr(
            g,
            "_taller_config",
            None
        )

        return {
            "css_vars": ConfiguracionService.css_vars(
                config
            )
        }

    @app.template_filter("img_thumb")
    def img_thumb_filter(
        ruta_publica: str | None
    ) -> str | None:

        return ImageService.thumb_url(
            ruta_publica
        )


# ==============================================================
# LOGIN
# ==============================================================

@login_manager.user_loader
def load_user(
    user_id: str
) -> Usuario | None:

    return db.session.get(
        Usuario,
        int(user_id)
    )


# ==============================================================
# LOCAL DEVELOPMENT
# ==============================================================

if __name__ == "__main__":

    app = create_app()

    app.run()