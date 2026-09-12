"""FASE 15 - Panel de ConfiguraciÃ³n Centralizado de SIAM."""
import json
from datetime import date, timedelta

import pytest

from database.db import db
from models import Cliente, ConfiguracionTaller, Usuario, Vehiculo
from models.historial_vehiculo import HistorialVehiculo
from models.recordatorio import Recordatorio
from services.configuracion_service import ConfiguracionService
from services.recordatorio_service import RecordatorioService

SECCIONES = ConfiguracionService.SECCIONES
SECCIONES_LECTURA = {"sedes", "archivos", "seguridad", "sistema"}


def _crear_usuario(db, correo, rol, nombre="Usuario"):
    u = Usuario(nombre=nombre, correo=correo, rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo, password="clave1234"):
    return client.post(
        "/auth/login", data={"correo": correo, "password": password}, follow_redirects=False
    )


def _ajax_headers():
    return {"Accept": "application/json"}


class TestPermisosPanel:
    def test_no_autenticado_redirige_login(self, client):
        r = client.get("/configuracion/empresa", follow_redirects=False)
        assert r.status_code == 302
        assert "/auth/login" in r.headers.get("Location", "")

    def test_cliente_redirige_portal(self, app, client):
        with app.app_context():
            _crear_usuario(db, "cli_cfg@test.com", "cliente")
        _login(client, "cli_cfg@test.com")
        r = client.get("/configuracion/empresa", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers.get("Location", "").endswith("/portal/")

    def test_index_redirige_a_empresa(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.get("/configuracion/", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers.get("Location", "").endswith("/configuracion/empresa")

    def test_staff_puede_leer_secciones_permitidas(self, app, client):
        with app.app_context():
            _crear_usuario(db, "recep_cfg@test.com", "recepcion")
            _crear_usuario(db, "mec_cfg@test.com", "mecanico")

        secciones_restringidas = {"archivos", "sistema", "seguridad"}

        for correo in ("recep_cfg@test.com", "mec_cfg@test.com"):
            _login(client, correo)

            for seccion in SECCIONES:
                r = client.get(f"/configuracion/{seccion}")

                if seccion in secciones_restringidas:
                    assert r.status_code == 302, (
                        f"{correo} no debería poder leer {seccion}"
                    )
                else:
                    assert r.status_code == 200, (
                        f"{correo} no pudo leer {seccion}"
                    )
    def test_admin_puede_leer_todas_las_secciones(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        for seccion in SECCIONES:
            r = client.get(f"/configuracion/{seccion}")
            assert r.status_code == 200, f"admin no pudo leer {seccion}"

    def test_seccion_desconocida_404(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        assert client.get("/configuracion/noexiste").status_code == 404

    def test_post_seccion_lectura_405(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        for seccion in SECCIONES_LECTURA:
            r = client.post(f"/configuracion/{seccion}")
            assert r.status_code == 405, f"POST {seccion} debÃ­a ser 405"


class TestEscrituraSoloAdmin:
    def test_staff_post_ajax_403(self, app, client):
        with app.app_context():
            _crear_usuario(db, "recep_cfg@test.com", "recepcion")
        _login(client, "recep_cfg@test.com")
        r = client.post(
            "/configuracion/apariencia",
            data={"color_primario": "#112233"},
            headers=_ajax_headers(),
        )
        assert r.status_code == 403
        assert r.get_json()["success"] is False

    def test_staff_post_form_redirige(self, app, client):
        with app.app_context():
            _crear_usuario(db, "recep_cfg@test.com", "recepcion")
        _login(client, "recep_cfg@test.com")
        r = client.post("/configuracion/apariencia", data={"color_primario": "#112233"})
        assert r.status_code == 302
        assert r.headers.get("Location", "").endswith("/configuracion/apariencia")

    def test_staff_quitar_logo_403(self, app, client):
        with app.app_context():
            _crear_usuario(db, "recep_cfg@test.com", "recepcion")
        _login(client, "recep_cfg@test.com")
        r = client.post("/configuracion/quitar-logo", headers=_ajax_headers())
        assert r.status_code == 403
        assert r.get_json()["success"] is False


class TestApariencia:
    def test_hex_valido_se_normaliza_y_persiste(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/configuracion/apariencia",
            data={
                "color_primario": "#a1b2c3",
                "color_primario_fuerte": "#0f0",
                "color_primario_soft": "#fff",
                "color_acento": "#0F766E",
            },
            headers=_ajax_headers(),
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            assert config.color_primario == "#A1B2C3"
            assert config.color_primario_fuerte == "#0F0"

    def test_hex_invalido_rechazado_400(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/configuracion/apariencia",
            data={"color_primario": "notacolor"},
            headers=_ajax_headers(),
        )
        assert r.status_code == 400
        assert r.get_json()["success"] is False
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            assert config.color_primario == "#2563EB"

    def test_css_vars_inyectadas_en_pagina(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
            config = ConfiguracionTaller.get_config()
            config.color_primario = "#112233"
            db.session.commit()
        _login(client, "admin_cfg@test.com")
        r = client.get("/configuracion/apariencia")
        html = r.get_data(as_text=True)
        assert "--siam-primary: #112233" in html


class TestPersistenciaSecciones:
    def test_empresa_guardar(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/configuracion/empresa",
            data={
                "nombre_taller": "Taller Central SAS",
                "nit": "900123456",
                "ciudad": "BogotÃ¡",
                "telefono": "555-0100",
                "whatsapp": "3001234567",
                "email": "info@tallercentral.co",
                "sitio_web": "https://tallercentral.co",
                "iva_porcentaje": "19.00",
            },
            headers=_ajax_headers(),
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            assert config.nombre_taller == "Taller Central SAS"
            assert config.ciudad == "BogotÃ¡"
            assert config.whatsapp == "3001234567"
            assert config.sitio_web == "https://tallercentral.co"

    def test_citas_guardar(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/configuracion/citas",
            data={
                "citas_intervalo_min": "60",
                "citas_min_anticipacion_horas": "4",
                "citas_cancelar_limite_horas": "8",
            },
            headers=_ajax_headers(),
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            assert config.citas_intervalo_min == 60
            assert config.citas_min_anticipacion_horas == 4
            assert config.citas_cancelar_limite_horas == 8

    def test_notificaciones_guardar(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/configuracion/notificaciones",
            data={
                "notif_email": "y",
                "notif_sms": "y",
                "notif_recordatorio_dias": "3",
            },
            headers=_ajax_headers(),
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            assert config.notif_email is True
            assert config.notif_sms is True
            assert config.notif_recordatorio_dias == 3

    def test_ia_guardar_preguntas(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/configuracion/ia",
            data={
                "ia_activado": "y",
                "ia_nombre": "Asistente SIAM",
                "ia_tono": "Amigable",
                "ia_mensaje_bienvenida": "Hola, Â¿en quÃ© te ayudo?",
                "ia_contacto": "WhatsApp 3001234567",
                "ia_preguntas_sugeridas": "Â¿CuÃ¡l es el horario?\nÂ¿CÃ³mo agendo una cita?",
            },
            headers=_ajax_headers(),
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            assert config.ia_nombre == "Asistente SIAM"
            assert config.ia_mensaje_bienvenida == "Hola, Â¿en quÃ© te ayudo?"
            preguntas = json.loads(config.ia_preguntas_sugeridas)
            assert preguntas == ["Â¿CuÃ¡l es el horario?", "Â¿CÃ³mo agendo una cita?"]

    def test_ia_get_muestra_preguntas_una_por_linea(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
            config = ConfiguracionTaller.get_config()
            config.ia_preguntas_sugeridas = json.dumps(
                ["Â¿CuÃ¡l es el horario?", "Â¿CÃ³mo agendo una cita?"], ensure_ascii=False
            )
            db.session.commit()
        _login(client, "admin_cfg@test.com")
        r = client.get("/configuracion/ia")
        html = r.get_data(as_text=True)
        assert "Â¿CuÃ¡l es el horario?\nÂ¿CÃ³mo agendo una cita?" in html


class TestSeguridadYEstado:
    def test_no_expone_secretos(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
            secret = app.config["SECRET_KEY"]
            uri = app.config["SQLALCHEMY_DATABASE_URI"]
        _login(client, "admin_cfg@test.com")
        for seccion in ("seguridad", "sistema"):
            html = client.get(f"/configuracion/{seccion}").get_data(as_text=True)
            assert secret not in html, f"SECRET_KEY expuesto en {seccion}"
            assert "DATABASE_URL" not in html, f"DATABASE_URL expuesto en {seccion}"
            assert "sqlite://" not in html, f"URI de BD expuesta en {seccion}"

    def test_seguridad_muestra_usuarios(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin", nombre="Admin")
            _crear_usuario(db, "recep_cfg@test.com", "recepcion", nombre="RecepciÃ³n")
        _login(client, "admin_cfg@test.com")
        html = client.get("/configuracion/seguridad").get_data(as_text=True)
        assert "admin_cfg@test.com" in html
        assert "recep_cfg@test.com" in html

    def test_login_registra_ultimo_acceso(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        with app.app_context():
            usuario = Usuario.query.filter_by(correo="admin_cfg@test.com").first()
            assert usuario.last_access_at is not None

    def test_sistema_get_muestra_version(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        html = client.get("/configuracion/sistema").get_data(as_text=True)
        assert "2.0.0" in html

    def test_sistema_comprobar(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post("/configuracion/sistema/comprobar", headers=_ajax_headers())
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        resultados = body["resultados"]
        assert len(resultados) >= 3
        nombres = [item["nombre"] for item in resultados]
        assert "Base de datos" in nombres
        for item in resultados:
            assert item["estado"] in ("verde", "amarillo", "rojo")
            assert item["detalle"]

    def test_quitar_logo_sin_logo_400(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        r = client.post("/configuracion/quitar-logo", headers=_ajax_headers())
        assert r.status_code == 400
        assert r.get_json()["success"] is False


class TestServicioYEnlaces:
    def test_hora_en_intervalo(self):
        from datetime import time

        assert ConfiguracionService.hora_en_intervalo(time(10, 0), 30) is True
        assert ConfiguracionService.hora_en_intervalo(time(10, 30), 30) is True
        assert ConfiguracionService.hora_en_intervalo(time(10, 45), 30) is False
        assert ConfiguracionService.hora_en_intervalo(time(10, 0), 60) is True
        assert ConfiguracionService.hora_en_intervalo(time(10, 30), 60) is False
        assert ConfiguracionService.hora_en_intervalo(time(10, 15), None) is True

    def test_sidebar_enlaza_panel(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        html = client.get("/configuracion/empresa").get_data(as_text=True)
        assert "/configuracion/empresa" in html

    def test_ruta_legacy_facturas_intacta(self, app, client):
        with app.app_context():
            _crear_usuario(db, "admin_cfg@test.com", "admin")
        _login(client, "admin_cfg@test.com")
        assert client.get("/facturas/configuracion").status_code == 200


class TestIntervaloCitasAplicado:
    def _setup(self, app):
        cliente = Cliente(nombre="Carlos", telefono="555")
        db.session.add(cliente)
        db.session.flush()
        db.session.add(
            Vehiculo(cliente_id=cliente.id, marca="Renault", modelo="Clio", placa="ABC123")
        )
        _crear_usuario(db, "admin_cfg@test.com", "admin")
        config = ConfiguracionTaller.get_config()
        config.citas_intervalo_min = 60
        db.session.commit()
        return (date.today() + timedelta(days=7)).isoformat()

    def test_cita_fuera_de_intervalo_rechazada(self, app, client):
        from models.cita import Cita

        with app.app_context():
            fecha = self._setup(app)
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/citas/crear",
            data={
                "cliente_id": "1",
                "vehiculo_id": "1",
                "fecha": fecha,
                "hora": "10:30",
            },
        )
        assert r.status_code == 200
        assert "no se ajusta" in r.get_data(as_text=True)
        with app.app_context():
            assert Cita.query.count() == 0

    def test_cita_dentro_de_intervalo_creada(self, app, client):
        from models.cita import Cita

        with app.app_context():
            fecha = self._setup(app)
        _login(client, "admin_cfg@test.com")
        r = client.post(
            "/citas/crear",
            data={
                "cliente_id": "1",
                "vehiculo_id": "1",
                "fecha": fecha,
                "hora": "10:00",
            },
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert r.headers.get("Location", "").endswith("/citas/")
        with app.app_context():
            assert Cita.query.count() == 1


class TestRecordatorioAnticipacionConfig:
    def test_dias_anticipacion_usa_config(self, app):
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            config.notif_recordatorio_dias = 15
            db.session.commit()
            assert RecordatorioService._dias_anticipacion() == 15

            config.notif_recordatorio_dias = 0
            db.session.commit()
            assert RecordatorioService._dias_anticipacion() == 3

    def test_generar_mantenimientos_respeta_anticipacion(self, app):
        with app.app_context():
            config = ConfiguracionTaller.get_config()
            config.notif_recordatorio_dias = 10
            cliente = Cliente(nombre="Ana", telefono="555")
            db.session.add(cliente)
            db.session.flush()
            vehiculo = Vehiculo(cliente_id=cliente.id, marca="Mazda", modelo="3", placa="XYZ999")
            db.session.add(vehiculo)
            db.session.flush()
            vehiculo_id = vehiculo.id
            db.session.add(
                HistorialVehiculo(
                    vehiculo_id=vehiculo_id,
                    tipo="cambio_aceite",
                    fecha=date.today() - timedelta(days=200),
                )
            )
            db.session.commit()

            RecordatorioService.generar_mantenimientos()

        with app.app_context():
            esperado = date.today() + timedelta(days=10)
            rec = Recordatorio.query.filter_by(
                vehiculo_id=vehiculo_id, tipo="mantenimiento"
            ).first()
            assert rec is not None
            assert rec.fecha_programada == esperado


