"""FASE 6/7 - Chat contextual: memoria entre mensajes y acciones clicables."""
from models import Usuario
from services.assistant_service import AssistantService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_ctx@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db):
    u = Usuario(nombre="Cliente", correo="cli_ctx@test.com", rol="cliente")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


class TestAccionesClicables:
    def test_cita_incluye_accion(self, db):
        u = _crear_cliente(db)
        r = AssistantService.process_message("quiero agendar una cita", usuario=u)
        assert "acciones" in r
        assert any(a["url"] == "/portal/citas/solicitar" for a in r["acciones"])

    def test_cita_staff_ruta_empresa(self, db):
        u = _crear_admin(db)
        r = AssistantService.process_message("quiero agendar una cita", usuario=u)
        assert any(a["url"] == "/citas/" for a in r["acciones"])

    def test_sedes_incluye_accion(self, db):
        u = _crear_cliente(db)
        r = AssistantService.process_message("cual es la sede mas cercana", usuario=u)
        assert any(a["url"] == "/sedes/" for a in r["acciones"])

    def test_asistencia_emergencia_incluye_accion(self, db):
        u = _crear_cliente(db)
        r = AssistantService.process_message("estoy varado", usuario=u)
        assert any(a["url"] == "/sedes/" for a in r["acciones"])

    def test_facturacion_cliente_dos_acciones(self, db):
        u = _crear_cliente(db)
        r = AssistantService.process_message("como facturo?", usuario=u)
        urls = [a["url"] for a in r.get("acciones", [])]
        assert "/portal/facturas" in urls
        assert "/portal/pagos" in urls

    def test_respuesta_incluye_intent(self):
        r = AssistantService.process_message("mi carro no prende")
        assert r.get("intent") == "diagnostico_arranque"

    def test_no_entiendo_sin_acciones(self):
        r = AssistantService.process_message("zxcvbn")
        assert not r.get("acciones")


class TestMemoriaContextual:
    def test_respuesta_corta_tras_cita(self, db):
        u = _crear_cliente(db)
        AssistantService.process_message("quiero una cita", usuario=u)
        r = AssistantService.process_message("si", usuario=u, contexto={"ultimo_intent": "cita_agendar"})
        assert "agendar tu cita" in r["text"].lower() or "de inmediato" in r["text"].lower()

    def test_respuesta_negativa(self, db):
        u = _crear_cliente(db)
        r = AssistantService.process_message("no", usuario=u, contexto={"ultimo_intent": "cita_agendar"})
        assert "no hay problema" in r["text"].lower()

    def test_followup_precio_tras_diagnostico(self):
        r = AssistantService.process_message(
            "y cuanto cuesta?", contexto={"ultimo_intent": "diagnostico_frenos"}
        )
        assert "precio" in r["text"].lower() or "valor" in r["text"].lower()

    def test_followup_sede(self):
        r = AssistantService.process_message(
            "donde quedan?", contexto={"ultimo_intent": "repuestos"}
        )
        assert "sedes" in r["text"].lower()

    def test_sin_contexto_no_rompe(self):
        r = AssistantService.process_message("hola")
        assert "text" in r


class TestChatEndpointContexto:
    def test_ask_devuelve_acciones_y_contexto(self, client, db):
        _crear_cliente(db)
        client.post("/auth/login", data={
            "correo": "cli_ctx@test.com", "password": "clave1234",
        }, follow_redirects=True)
        resp = client.post("/asistente/ask", json={"mensaje": "quiero una cita"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["intent"] == "cita_agendar"
        assert data["acciones"]
        assert data["acciones"][0]["url"] == "/portal/citas/solicitar"

    def test_ask_memoria_sesion(self, client, db):
        _crear_cliente(db)
        client.post("/auth/login", data={
            "correo": "cli_ctx@test.com", "password": "clave1234",
        }, follow_redirects=True)
        client.post("/asistente/ask", json={"mensaje": "quiero una cita"})
        resp = client.post("/asistente/ask", json={"mensaje": "si"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "agendar tu cita" in data["respuesta"].lower() or "de inmediato" in data["respuesta"].lower()
