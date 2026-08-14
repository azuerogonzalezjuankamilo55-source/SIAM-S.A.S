"""FASE 3 - Asistente IA: pruebas de intents, seguridad y chat."""
from models import Usuario
from services.assistant_service import AssistantService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_asist@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db, correo="cliente_asist@test.com"):
    u = Usuario(nombre="Cliente", correo=correo, rol="cliente")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


class TestIntents:
    def test_no_prende(self):
        r = AssistantService.process_message("mi carro no prende")
        assert "El veh\u00edculo no arranca" in r["text"]

    def test_moto_se_apaga(self):
        r = AssistantService.process_message("la moto se est\u00e1 apagando")
        assert "se apaga en marcha" in r["text"]

    def test_carro_vibra(self):
        r = AssistantService.process_message("\u00bfpor qu\u00e9 mi carro vibra?")
        assert "Vibraciones" in r["text"]

    def test_cambio_aceite_cada_cuanto(self):
        r = AssistantService.process_message("\u00bfcada cu\u00e1nto debo cambiar el aceite?")
        assert "Mantenimiento preventivo" in r["text"]

    def test_carro_se_calienta(self):
        r = AssistantService.process_message("mi carro se est\u00e1 calentando")
        assert "El veh\u00edculo se calienta" in r["text"]

    def test_check_engine(self):
        r = AssistantService.process_message("\u00bfqu\u00e9 significa el Check Engine?")
        assert "Testigo de motor" in r["text"]

    def test_que_aceite_usa(self):
        r = AssistantService.process_message("\u00bfqu\u00e9 aceite usa mi carro?")
        assert "El tipo de aceite correcto" in r["text"]

    def test_estoy_varado(self):
        r = AssistantService.process_message("estoy varado")
        assert "asistencia" in r["text"].lower()

    def test_quiero_cita(self):
        r = AssistantService.process_message("quiero una cita")
        assert "agendar una cita" in r["text"]

    def test_sede_cercana(self):
        r = AssistantService.process_message("\u00bfcu\u00e1l es la sede m\u00e1s cercana?")
        assert "m\u00e1s cercana" in r["text"] or "sedes" in r["text"].lower()

    def test_cuanto_cuesta_revision(self):
        r = AssistantService.process_message("\u00bfcu\u00e1nto cuesta una revisi\u00f3n?")
        assert "revisi\u00f3n" in r["text"].lower() or "precio" in r["text"].lower()

    def test_tienen_repuestos_motos(self):
        r = AssistantService.process_message("tienen repuestos para motos")
        assert "repuesto" in r["text"].lower() or "inventario" in r["text"].lower()

    def test_atienden_camiones(self):
        r = AssistantService.process_message("\u00bfatienden camiones?")
        assert "carga" in r["text"].lower()

    def test_respuesta_siempre_tiene_text(self):
        frases = [
            "hola", "gracias", "se me pinch\u00f3 una llanta",
            "la moto no acelera", "mi carro echa humo blanco",
            "qu\u00e9 hacen en el taller", "necesito ayuda",
        ]
        for frase in frases:
            r = AssistantService.process_message(frase)
            assert isinstance(r, dict)
            assert "text" in r

    def test_cuando_debo_cambiar_aceite(self):
        r = AssistantService.process_message("cu\u00e1ndo debo cambiar el aceite")
        assert "Mantenimiento preventivo" in r["text"]

    def test_llevar_carro_al_taller(self):
        r = AssistantService.process_message("quiero llevar mi carro al taller")
        assert "agendar una cita" in r["text"]

    def test_huele_a_gasolina(self):
        r = AssistantService.process_message("mi carro huele a gasolina")
        texto = r["text"].lower()
        assert ("seguridad" in texto or "riesgo" in texto or "det\u00e9n" in texto
                or "no contin\u00faes" in texto or "varado" in texto)

    def test_facturacion(self):
        r = AssistantService.process_message("\u00bfc\u00f3mo facturo?")
        assert "factura" in r["text"].lower()

    def test_cliente_facturacion(self, db):
        _crear_cliente(db)
        u = Usuario.query.filter_by(correo="cliente_asist@test.com").first()
        r = AssistantService.process_message("\u00bfc\u00f3mo facturo?", usuario=u)
        assert "portal de cliente" in r["text"].lower()


class TestSeguridad:
    def test_no_diagnostico_definitivo(self):
        r = AssistantService.process_message("mi carro no prende")
        texto = r["text"].lower()
        assert "podr\u00eda deberse" in texto or "una posible causa" in texto
        assert "no puedo dar un diagn\u00f3stico definitivo" in texto

    def test_peligro_incendio(self):
        r = AssistantService.process_message("mi carro est\u00e1 echando humo y huele a gasolina")
        texto = r["text"].lower()
        assert ("det\u00e9n" in texto or "deten" in texto or "no contin\u00faes" in texto
                or "seguridad" in texto or "riesgo" in texto)

    def test_no_inventa_precios(self):
        r = AssistantService.process_message("\u00bfcu\u00e1nto cuesta un turbo de formula uno 2099?")
        texto = r["text"].lower()
        assert ("no dispongo del precio" in texto or "contactar a siam" in texto
                or "no dispongo" in texto or "cotizaci" in texto)

    def test_cliente_no_ve_datos_admin(self, db):
        _crear_cliente(db)
        u = Usuario.query.filter_by(correo="cliente_asist@test.com").first()
        r = AssistantService.process_message("\u00bfcu\u00e1ntos clientes hay?", usuario=u)
        assert "administrativa" in r["text"].lower() or "personal autorizado" in r["text"].lower()

    def test_admin_si_ve_contadores(self, db):
        _crear_admin(db)
        u = Usuario.query.filter_by(correo="admin_asist@test.com").first()
        r = AssistantService.process_message("\u00bfcu\u00e1ntos clientes hay?", usuario=u)
        assert "clientes" in r["text"].lower()


class TestChatEndpoint:
    def test_ask_requiere_login(self, client):
        resp = client.post("/asistente/ask", json={"mensaje": "hola"})
        assert resp.status_code in (401, 302)

    def test_ask_responde(self, client, db):
        _crear_admin(db)
        client.post("/auth/login", data={
            "correo": "admin_asist@test.com", "password": "admin123",
        }, follow_redirects=True)
        resp = client.post("/asistente/ask", json={"mensaje": "mi carro no prende"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "respuesta" in data
        assert "El veh\u00edculo no arranca" in data["respuesta"]

    def test_ask_mensaje_vacio(self, client, db):
        _crear_admin(db)
        client.post("/auth/login", data={
            "correo": "admin_asist@test.com", "password": "admin123",
        }, follow_redirects=True)
        resp = client.post("/asistente/ask", json={"mensaje": ""})
        assert resp.status_code == 400

    def test_asistente_pagina(self, client, db):
        _crear_admin(db)
        client.post("/auth/login", data={
            "correo": "admin_asist@test.com", "password": "admin123",
        }, follow_redirects=True)
        resp = client.get("/asistente/")
        assert resp.status_code == 200
        assert b"Asistente" in resp.data
