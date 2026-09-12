"""FASE 10.4 - Correcciones finales de producción.

Cubre los 6 problemas reportados en la fase:
1. Accesos separados en la principal (administrador + personal taller, cliente,
   registro) reutilizando rutas existentes.
2. Botón de notificaciones estable (posición fija, sin transition:all, refresco
   inmediato del badge al leer).
3. Geolocalización con Leaflet/OpenStreetMap/OSRM (ruta, distancia, ETA y
   autofit en el portal) sin Google Maps API.
4. Registro sin Internal Server Error: mensajes amigables, excepción real
   logueada y protección ante errores de unicidad.
5. Despliegue en Render: Procfile/render.yaml con Gunicorn 'app:create_app()'.
6. Compatibilidad de producción: HTTPS, cookies seguras, CSRF y PostgreSQL.
"""
import logging
import pathlib

import pytest
from sqlalchemy.exc import IntegrityError

from models import Usuario, Cliente, Cita, Vehiculo, UbicacionCliente
from app import create_app

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PASS = "clave1234"


# ============================================================
# Helpers
# ============================================================

def _crear_usuario(db, rol, correo, cliente=None):
    u = Usuario(nombre=rol, correo=correo, rol=rol, cliente_id=cliente.id if cliente else None)
    u.set_password(PASS)
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db, correo="cliente_f104@test.com", cedula=None):
    c = Cliente(nombre="Cliente F104", correo=correo, telefono="3001112222", cedula=cedula)
    db.session.add(c)
    db.session.commit()
    return c


def _login(client, correo, password=PASS):
    return client.post(
        "/auth/login",
        data={"correo": correo, "password": password},
        follow_redirects=False,
    )


def _registro_data(correo, documento="1090999999", telefono="3001112222"):
    return {
        "nombre": "Nuevo Cliente F104",
        "documento": documento,
        "correo": correo,
        "telefono": telefono,
        "password": PASS,
        "confirmar_password": PASS,
    }


# ============================================================
# 1. Accesos separados en la principal
# ============================================================

class TestAccesosSeparados:

    def test_landing_muestra_tres_opciones(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Ingresar como administrador" in html
        assert "Ingresar como cliente" in html
        assert "Registrarme como cliente" in html
        # Reutiliza las rutas existentes con su área.
        assert "auth/login?area=admin" in html
        assert "auth/login?area=cliente" in html
        assert "auth/register" in html

    def test_area_admin_incluye_personal_taller(self, client, db):
        _crear_usuario(db, "recepcion", "recepcion_f104@test.com")
        resp = client.get("/auth/login?area=admin")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Área administrativa" in html
        # Un usuario de recepción entra al panel con las mismas credenciales.
        login = _login(client, "recepcion_f104@test.com")
        assert login.status_code in (301, 302, 303)
        assert "/dashboard" in login.headers.get("Location", "")
        seguir = client.post(
            "/auth/login",
            data={"correo": "recepcion_f104@test.com", "password": PASS},
            follow_redirects=True,
        )
        assert b"Dashboard" in seguir.data

    def test_area_cliente_redirige_al_portal(self, client, db):
        c = _crear_cliente(db)
        _crear_usuario(db, "cliente", c.correo, cliente=c)
        resp = client.get("/auth/login?area=cliente")
        assert resp.status_code == 200
        assert "Acceso clientes" in resp.get_data(as_text=True)
        login = client.post(
            "/auth/login",
            data={"correo": c.correo, "password": PASS},
            follow_redirects=True,
        )
        assert b"Mi Portal" in login.data


# ============================================================
# 2. Botón de notificaciones estable
# ============================================================

class TestBotonNotificaciones:
    """El botón de la campana queda fijo, su badge es absoluto y no hay
    transición de layout que lo desplace."""

    def test_campana_presente_en_panel_autenticado(self, client, db):
        _crear_usuario(db, "admin", "admin_notif@test.com")
        client.post(
            "/auth/login",
            data={"correo": "admin_notif@test.com", "password": PASS},
        )
        resp = client.get("/dashboard/")
        html = resp.get_data(as_text=True)
        assert 'id="notifToggle"' in html
        assert 'id="notifBadge"' in html
        # Sin notificaciones aún, el badge está oculto (d-none) y no movió nada.
        assert 'class="badge bg-danger d-none" id="notifBadge"' in html

    def test_css_sin_transition_all_en_boton(self):
        css = (RAIZ / "static" / "css" / "navbar.css").read_text(encoding="utf-8")
        bloque = css.split(".navbar-icon-btn")[1]
        # El botón (campana/tema/salir) solo transiciona color, jamás layout.
        assert "transition: all" not in bloque
        assert "transition: background-color" in bloque
        assert ".navbar-icon-btn .badge" in css
        assert "position: absolute;" in css

    def test_js_refresca_badge_al_marcar_leida(self):
        js = (RAIZ / "static" / "js" / "siam.js").read_text(encoding="utf-8")
        assert "if (d && d.success) cargar()" in js
        assert "setInterval(cargar, 60000)" in js


# ============================================================
# 3. Geolocalización Leaflet/OSM/OSRM
# ============================================================

class TestGeolocalizacionOSRM:

    def test_portal_usa_leaflet_osm_osrm_y_ruta(self, client, db):
        c = _crear_cliente(db)
        u = _crear_usuario(db, "cliente", c.correo, cliente=c)
        client.post("/auth/login", data={"correo": u.correo, "password": PASS})
        resp = client.get("/portal/")
        html = resp.get_data(as_text=True)
        assert "unpkg.com/leaflet@1.9.4" in html
        assert "tile.openstreetmap.org" in html
        assert "/api/ubicacion/ruta" in html
        assert "navigator.geolocation" in html
        assert "fitBounds" in html
        assert "infoMiRuta" in html
        assert "distancia" in html.lower() or "Llegada" in html

    def test_sin_google_ni_api_key(self, client, db):
        c = _crear_cliente(db, correo="sin_google@test.com")
        u = _crear_usuario(db, "cliente", c.correo, cliente=c)
        client.post("/auth/login", data={"correo": u.correo, "password": PASS})
        for ruta in ("/portal/", "/sedes"):
            html = client.get(ruta).get_data(as_text=True)
            assert "maps.googleapis" not in html
            assert "google.maps" not in html
            assert "GOOGLE_MAPS_API_KEY" not in html

    def test_ruta_sin_compartir_responde_json_amigable(self, client, db):
        c = _crear_cliente(db, correo="sin_compartir@test.com")
        u = _crear_usuario(db, "cliente", c.correo, cliente=c)
        client.post("/auth/login", data={"correo": u.correo, "password": PASS})
        resp = client.get("/api/ubicacion/ruta")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["ok"] is False

    def test_ruta_con_ubicacion_activa(self, client, db):
        from datetime import date, time
        c = _crear_cliente(db, correo="comparte_f104@test.com")
        u = _crear_usuario(db, "cliente", c.correo, cliente=c)
        v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="RUT-104")
        db.session.add(v)
        db.session.commit()
        cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0), estado="confirmada")
        db.session.add(cita)
        db.session.commit()
        loc = UbicacionCliente(
            cliente_id=c.id, cita_id=cita.id, latitude=4.62, longitude=-74.12,
            accuracy=20.0, sharing_active=True,
        )
        db.session.add(loc)
        db.session.commit()
        client.post("/auth/login", data={"correo": u.correo, "password": PASS})
        resp = client.get("/api/ubicacion/ruta")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        # Tests sin OSRM configurado (red desactivada): ok=False y no rompe.
        assert data["ok"] is False

    def test_staff_no_usa_ruta_de_cliente(self, client, db):
        _crear_usuario(db, "admin", "admin_ruta@test.com")
        client.post("/auth/login", data={"correo": "admin_ruta@test.com", "password": PASS})
        resp = client.get("/api/ubicacion/ruta")
        assert resp.status_code == 403
        assert resp.get_json()["success"] is False


# ============================================================
# 4. Registro sin Internal Server Error
# ============================================================

class TestRegistroSin500:

    def test_registro_happy_path_crea_cliente(self, client, db):
        resp = client.post("/auth/register", data=_registro_data("nuevo_f104@test.com"),
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b"Mi Portal" in resp.data
        u = Usuario.query.filter_by(correo="nuevo_f104@test.com").first()
        assert u is not None
        assert u.rol == "cliente"
        assert u.cliente_id is not None
        assert db.session.get(Cliente, u.cliente_id).cedula == "1090999999"

    def test_correo_duplicado_amigable(self, client, db):
        _crear_usuario(db, "cliente", "dup_f104@test.com")
        resp = client.post("/auth/register", data=_registro_data("dup_f104@test.com"),
                           follow_redirects=True)
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "El correo ya está registrado" in html
        # No se creó una segunda cuenta.
        assert Usuario.query.filter_by(correo="dup_f104@test.com").count() == 1

    def test_documento_ajeno_amigable(self, client, db):
        _crear_cliente(db, correo="otro_f104@test.com", cedula="99990000")
        resp = client.post("/auth/register", data=_registro_data("nuevo_doc@test.com", documento="99990000"),
                           follow_redirects=True)
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "Ese documento ya está registrado" in html
        assert Usuario.query.filter_by(correo="nuevo_doc@test.com").first() is None

    def test_error_integridad_amigable(self, client, db, monkeypatch):
        def _boom(*args, **kwargs):
            raise IntegrityError("INSERT", {}, Exception("duplicate key value"))

        monkeypatch.setattr("routes.auth.safe_commit", _boom)
        resp = client.post("/auth/register", data=_registro_data("integrity_f104@test.com"),
                           follow_redirects=True)
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "No se pudo completar el registro. Intenta nuevamente." in html
        assert Usuario.query.filter_by(correo="integrity_f104@test.com").first() is None

    def test_error_generico_db_amigable(self, client, db, monkeypatch):
        def _boom(*args, **kwargs):
            raise RuntimeError("locked database")

        monkeypatch.setattr("routes.auth.safe_commit", _boom)
        resp = client.post("/auth/register", data=_registro_data("generic_f104@test.com"),
                           follow_redirects=True)
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "No se pudo completar el registro. Intenta nuevamente." in html


# ============================================================
# Permisos por rol
# ============================================================

class TestPermisosRol:

    def test_cliente_bloqueado_del_dashboard(self, client, db):
        c = _crear_cliente(db, correo="block_f104@test.com")
        u = _crear_usuario(db, "cliente", c.correo, cliente=c)
        _login(client, u.correo)
        resp = client.get("/dashboard/")
        assert resp.status_code in (301, 302, 303)
        assert "/portal" in resp.headers.get("Location", "")

    def test_cliente_bloqueado_del_api_staff(self, client, db):
        c = _crear_cliente(db, correo="blockapi_f104@test.com")
        u = _crear_usuario(db, "cliente", c.correo, cliente=c)
        _login(client, u.correo)
        resp = client.get("/api/admin/clientes-en-camino")
        assert resp.status_code in (301, 302, 303)
        assert "/portal" in resp.headers.get("Location", "")

    def test_staff_si_accede_al_dashboard(self, client, db):
        for rol in ("admin", "recepcion", "mecanico"):
            correo = f"{rol}_dash_f104@test.com"
            _crear_usuario(db, rol, correo)
            client.post("/auth/login", data={"correo": correo, "password": PASS})
            resp = client.get("/dashboard/")
            assert resp.status_code == 200, rol


# ============================================================
# 5. Despliegue en Render
# ============================================================

class TestDeployRender:

    def test_procfile_comando_gunicorn(self):
        procfile = (RAIZ / "Procfile").read_text(encoding="utf-8")
        assert "gunicorn 'app:create_app()'" in procfile
        assert "--bind 0.0.0.0:$PORT" in procfile
        assert "--workers 4" in procfile
        assert "--timeout 120" in procfile
        assert "--log-level info" in procfile

    def test_render_yaml_comandos(self):
        yaml_ = (RAIZ / "render.yaml").read_text(encoding="utf-8")
        assert "gunicorn 'app:create_app()'" in yaml_
        assert "--log-level info" in yaml_
        assert "flask db upgrade" in yaml_
        assert "./render-build.sh" in yaml_
        assert "siam.onrender.com" in yaml_

    def test_requirements_servidor_y_db(self):
        req = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
        assert "gunicorn" in req
        assert "psycopg2-binary" in req
        assert "Flask" in req


# ============================================================
# 6. Compatibilidad de producción
# ============================================================

class TestProduccion:

    def test_config_produccion(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "clave-produccion-tests")
        monkeypatch.setenv("DATABASE_URL", "sqlite://")
        app = create_app("production")
        assert app.config["DEBUG"] is False
        assert app.config["SESSION_COOKIE_SECURE"] is True
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
        assert app.config["PREFERRED_URL_SCHEME"] == "https"
        assert app.config["WTF_CSRF_ENABLED"] is True

    def test_headers_seguridad_produccion(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "clave-produccion-tests")
        monkeypatch.setenv("DATABASE_URL", "sqlite://")
        app = create_app("production")
        with app.test_client() as c:
            resp = c.get("/health")
            assert "Strict-Transport-Security" in resp.headers
            assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]
            assert resp.headers["X-Content-Type-Options"] == "nosniff"
            assert "Content-Security-Policy" in resp.headers
            # Geolocalización permitida solo en el propio origen (HTTPS).
            assert "geolocation=(self)" in resp.headers["Permissions-Policy"]

    def test_runtime_python(self):
        rt = (RAIZ / "runtime.txt").read_text(encoding="utf-8").strip()
        assert rt.startswith("python-3.")


# ============================================================
# Causa raíz del fallo en Render: BD sin esquema (aún sin migrar).
# Antes, /auth/login?area=* devolvía 500 en
#   routes/auth.py (Usuario.query.filter_by(rol="admin").count())
# porque el GET consultaba la BD sin protección. Ahora las rutas públicas
# degradan con gracia (igual que "/" y /health) y loguean la excepción real.
# ============================================================

class TestDegradacionSinEsquema:
    # Reproduce el escenario de Render con una base REALMENTE vacía
    # (sin tablas, como un despliegue que aún no ejecutó flask db upgrade).
    # Se parchea la clase ProductionConfig antes de crear la app para que el
    # engine se construya contra la base vacía (monkeypatch restaura después).

    def _app_con_bd_vacia(self, monkeypatch, tmp_path):
        from config import ProductionConfig

        db_path = tmp_path / "vacia.db"
        monkeypatch.setenv("SECRET_KEY", "clave-produccion-tests")
        monkeypatch.setattr(
            ProductionConfig,
            "SQLALCHEMY_DATABASE_URI",
            f"sqlite:///{db_path.as_posix()}",
        )
        return create_app("production")

    def test_login_y_registro_sin_500_con_bd_vacia(self, monkeypatch, tmp_path):
        app = self._app_con_bd_vacia(monkeypatch, tmp_path)
        with app.test_client() as c:
            assert c.get("/health").status_code == 200
            assert c.get("/").status_code == 200
            assert c.get("/auth/register").status_code == 200
            assert c.get("/auth/login?area=admin").status_code == 200
            assert c.get("/auth/login?area=cliente").status_code == 200
            # Fail-closed: jamás se permite bootstrap admin con BD incierta.
            assert c.get("/auth/registrar-admin").status_code in (301, 302, 303)

    def test_excepcion_real_queda_en_log(self, monkeypatch, tmp_path):
        import traceback
        from routes import auth as auth_routes

        capturados: list[str] = []
        class _Captura(logging.Handler):
            def emit(self, record):
                msg = record.getMessage()
                if record.exc_info:
                    msg += "".join(traceback.format_exception(*record.exc_info))
                capturados.append(msg)

        cap = _Captura()
        auth_routes.logger.addHandler(cap)
        try:
            app = self._app_con_bd_vacia(monkeypatch, tmp_path)
            with app.test_client() as c:
                c.get("/auth/login?area=admin")
            detalle = " ".join(capturados).lower()
            assert any(
                marcador in detalle
                for marcador in ("no such table", "does not exist", "operationalerror")
            )
        finally:
            auth_routes.logger.removeHandler(cap)