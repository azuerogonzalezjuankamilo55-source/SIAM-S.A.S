"""FASE 16 - Flujos reales cliente -> taller y aislamiento de datos (IDOR).

Cubre lo que se corrigio en la seccion 26:
- el vehiculo de una solicitud de asistencia es real y pertenece al cliente,
- el taller ve quien solicito y con que vehiculo,
- los cambios de estado avisan al cliente,
- ningun cliente alcanza datos de otro cambiando un id en la peticion.
"""
import json

import pytest

from models import Usuario, Cliente, Vehiculo, Notificacion, AsistenciaEmergencia
from routes.sedes import AVISOS_ASISTENCIA
from services.notification_service import NotificationService
from services.vehiculo_service import VehiculoService


# ---------------------------------------------------------------- helpers


def _crear_usuario(db, correo, rol, nombre="Usuario", cliente_id=None):
    u = Usuario(nombre=nombre, correo=correo, rol=rol, cliente_id=cliente_id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.flush()
    return u


def _crear_cliente_con_usuario(db, nombre, slug):
    cli = Cliente(nombre=nombre, telefono="3001234567")
    db.session.add(cli)
    db.session.flush()
    u = _crear_usuario(db, f"{slug}@test.com", "cliente", nombre=nombre, cliente_id=cli.id)
    db.session.commit()
    return cli, u


def _crear_vehiculo(db, cli, placa, anio=2022, tipo="carro"):
    # `tipo` debe ser uno de Vehiculo.TIPOS: no se inventan valores.
    assert tipo in Vehiculo.TIPOS, f"tipo invalido: {tipo}"
    v = Vehiculo(
        cliente_id=cli.id,
        placa=placa,
        marca="Chevrolet",
        modelo="Onix",
        anio=anio,
        tipo=tipo,
    )
    db.session.add(v)
    db.session.commit()
    return v


def _crear_staff(db, slug, rol="admin"):
    return _crear_usuario(db, f"{slug}@test.com", rol, nombre=f"Staff {slug}")


def _login(client, correo, password="clave1234"):
    return client.post(
        "/auth/login",
        data={"correo": correo, "password": password},
        follow_redirects=True,
    )


def _post_json(client, url, payload):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"X-CSRFToken": "x", "Accept": "application/json"},
    )


# ------------------------------------------------------- vehiculo real


class TestVehiculoIdentificacion:
    def test_descriptor_usa_datos_reales(self, db):
        cli, _ = _crear_cliente_con_usuario(db, "Dueño", "desc1")
        v = _crear_vehiculo(db, cli, "ABC123", anio=2022, tipo="carro")
        texto = VehiculoService.descriptor(v)
        assert "ABC123" in texto
        assert "Chevrolet" in texto and "Onix" in texto
        assert "2022" in texto

    def test_descriptor_no_inventa_datos(self, db):
        cli, _ = _crear_cliente_con_usuario(db, "Sin extras", "desc2")
        v = Vehiculo(cliente_id=cli.id, placa="XYZ789", marca="Kia", modelo="Rio", anio=None)
        db.session.add(v)
        db.session.commit()
        texto = VehiculoService.descriptor(v)
        # Sin anio no se imprime "None" ni un placeholder.
        assert "undefined" not in texto and "None" not in texto and "N/A" not in texto
        # El tipo viene del default real del modelo, no de un supuesto.
        assert texto == "XYZ789 - Kia Rio - Carro"

    def test_descriptor_vehiculo_none(self):
        assert VehiculoService.descriptor(None) == ""

    def test_listar_para_select_texto_y_campos(self, db):
        cli, _ = _crear_cliente_con_usuario(db, "Selector", "desc3")
        v = _crear_vehiculo(db, cli, "SEL111")
        item = VehiculoService.listar_para_select(cli.id)[0]
        assert item["id"] == v.id
        assert item["placa"] == "SEL111"
        assert item["texto"] == VehiculoService.descriptor(v)


# ------------------------------------------- selector propio del cliente


class TestVehiculosMios:
    def test_requiere_login(self, client):
        resp = client.get("/api/vehiculos/mios")
        assert resp.status_code == 302

    def test_solo_devuelve_sus_vehiculos(self, client, db):
        cli1, _ = _crear_cliente_con_usuario(db, "Cliente Uno", "vm1")
        cli2, _ = _crear_cliente_con_usuario(db, "Cliente Dos", "vm2")
        v1 = _crear_vehiculo(db, cli1, "AAA-11")
        _crear_vehiculo(db, cli2, "BBB-22")

        _login(client, "vm1@test.com")
        resp = client.get("/api/vehiculos/mios")
        assert resp.status_code == 200
        placas = [x["placa"] for x in resp.get_json()]
        assert placas == [v1.placa]
        assert "BBB-22" not in placas

    def test_usuario_sin_cliente_devuelve_lista_vacia(self, client, db):
        _crear_usuario(db, "sincli@test.com", "cliente", nombre="Sin Cliente")
        db.session.commit()
        _login(client, "sincli@test.com")
        resp = client.get("/api/vehiculos/mios")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ------------------------------------------------- round trip asistencia


class TestRoundTripAsistencia:
    def test_cliente_crea_solicitud_con_vehiculo_y_taller_la_ve(self, client, db):
        cli, usuario = _crear_cliente_con_usuario(db, "Ana Cliente", "rt1")
        v = _crear_vehiculo(db, cli, "RT-001")
        staff = _crear_staff(db, "rt_staff", "admin")
        db.session.commit()

        _login(client, "rt1@test.com")
        resp = _post_json(client, "/api/asistencia", {
            "descripcion": "Se quedó sin batería en la vía",
            "latitude": 4.7110,
            "longitude": -74.0721,
            "vehiculo_id": v.id,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["vehiculo"] == VehiculoService.descriptor(v)

        # La solicitud quedo persistida y asociada al cliente y vehiculo reales.
        solicitud = db.session.get(AsistenciaEmergencia, data["id"])
        assert solicitud.cliente_id == cli.id
        assert solicitud.vehiculo_id == v.id
        assert solicitud.usuario_id == usuario.id
        assert solicitud.estado == "pendiente"
        assert solicitud.vehiculo_label == VehiculoService.descriptor(v)

        # El taller fue notificado y puede ver el contexto completo.
        avisos = NotificationService.list_for(staff.id)
        assert any(n.tipo == "asistencia" for n in avisos)
        assert any(v.placa in (n.mensaje or "") for n in avisos)

    def test_taller_ve_la_solicitud_en_su_panel(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Panel Cliente", "rt2")
        v = _crear_vehiculo(db, cli, "RT-002")
        _crear_staff(db, "rt2_staff", "recepcion")
        db.session.commit()

        _login(client, "rt2@test.com")
        _post_json(client, "/api/asistencia", {
            "descripcion": "Varado en el norte",
            "latitude": 4.70, "longitude": -74.07, "vehiculo_id": v.id,
        })

        client.get("/auth/logout", follow_redirects=True)
        _login(client, "rt2_staff@test.com")
        resp = client.get("/sedes/asistencias")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", "ignore")
        assert v.placa in body
        assert "Panel Cliente" in body
        assert "Varado en el norte" in body

    def test_ubicacion_crea_solicitud_asociada(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Geo Cliente", "rt3")
        v = _crear_vehiculo(db, cli, "RT-003")
        db.session.commit()

        _login(client, "rt3@test.com")
        resp = _post_json(client, "/api/ubicacion", {
            "latitude": 4.7110, "longitude": -74.0721,
            "accuracy": 12, "vehiculo_id": v.id,
        })
        assert resp.status_code == 200
        solicitud = db.session.get(AsistenciaEmergencia, resp.get_json()["id"])
        assert solicitud.cliente_id == cli.id
        assert solicitud.vehiculo_id == v.id

    def test_solicitud_sin_vehiculo_es_valida(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Sin Vehiculo", "rt4")
        db.session.commit()
        _login(client, "rt4@test.com")
        resp = _post_json(client, "/api/asistencia", {
            "descripcion": "Ayuda general",
            "latitude": 4.71, "longitude": -74.07,
        })
        assert resp.status_code == 200
        solicitud = db.session.get(AsistenciaEmergencia, resp.get_json()["id"])
        assert solicitud.vehiculo_id is None
        assert solicitud.cliente_id == cli.id
        assert solicitud.vehiculo_label == ""

    def test_cliente_ve_sus_propias_solicitudes(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Lista Cliente", "rt5")
        _crear_staff(db, "rt5_staff")
        db.session.commit()
        _login(client, "rt5@test.com")
        _post_json(client, "/api/asistencia", {
            "descripcion": "Primera", "latitude": 4.71, "longitude": -74.07,
        })
        resp = client.get("/api/asistencia")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1


# ----------------------------------------------- estados y notificacion


class TestEstadosAsistencia:
    @pytest.mark.parametrize("estado", ["en_camino", "atendido", "cancelado"])
    def test_taller_avisa_al_cliente(self, client, db, estado):
        cli, usuario = _crear_cliente_con_usuario(db, "Aviso", f"est_{estado}")
        _crear_staff(db, f"est_staff_{estado}", "admin")
        db.session.commit()

        _login(client, f"est_{estado}@test.com")
        r = _post_json(client, "/api/asistencia", {
            "descripcion": "Prueba", "latitude": 4.71, "longitude": -74.07,
        })
        solicitud_id = r.get_json()["id"]

        client.get("/auth/logout", follow_redirects=True)
        _login(client, f"est_staff_{estado}@test.com")
        resp = client.post(
            f"/sedes/asistencias/{solicitud_id}/estado",
            data=json.dumps({"estado": estado}),
            content_type="application/json",
            headers={"X-CSRFToken": "x", "Accept": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        solicitud = db.session.get(AsistenciaEmergencia, solicitud_id)
        assert solicitud.estado == estado

        avisos = NotificationService.list_for(usuario.id)
        # El aviso recibido es exactamente el que el taller debe enviar, con el
        # texto del estado nuevo (no basta con que exista "alguna" notificacion).
        titulo_esperado, _ = AVISOS_ASISTENCIA[estado]
        assert any(n.tipo == "asistencia" and n.titulo == titulo_esperado for n in avisos)

    def test_cliente_cancela_y_avisa_al_taller(self, client, db):
        _, _ = _crear_cliente_con_usuario(db, "Cancela", "can1")
        staff = _crear_staff(db, "can1_staff")
        db.session.commit()

        _login(client, "can1@test.com")
        r = _post_json(client, "/api/asistencia", {
            "descripcion": "Ya no necesito", "latitude": 4.71, "longitude": -74.07,
        })
        aid = r.get_json()["id"]
        resp = _post_json(client, f"/api/asistencia/{aid}/cancelar", {})
        assert resp.status_code == 200
        assert db.session.get(AsistenciaEmergencia, aid).estado == "cancelado"
        assert any(n.tipo == "asistencia" for n in NotificationService.list_for(staff.id))

    def test_cliente_no_puede_cambiar_estado(self, client, db):
        _crear_cliente_con_usuario(db, "Intruso Estado", "can2")
        _crear_staff(db, "can2_staff")
        db.session.commit()
        _login(client, "can2_staff@test.com")
        r = _post_json(client, "/api/asistencia", {
            "descripcion": "Mia", "latitude": 4.71, "longitude": -74.07,
        })
        aid = r.get_json()["id"]
        client.get("/auth/logout", follow_redirects=True)
        _login(client, "can2@test.com")
        resp = _post_json(
            client, f"/sedes/asistencias/{aid}/estado", {"estado": "atendido"}
        )
        # El panel es solo de personal: el cliente no entra.
        assert resp.status_code in (302, 403)
        assert db.session.get(AsistenciaEmergencia, aid).estado == "pendiente"


# --------------------------------------------------------------- IDOR


class TestAislamientoDatos:
    def test_no_puede_asociar_vehiculo_ajeno(self, client, db):
        cli1, _ = _crear_cliente_con_usuario(db, "Dueño Vehículo", "idor1")
        cli2, _ = _crear_cliente_con_usuario(db, "Intruso", "idor2")
        v_ajeno = _crear_vehiculo(db, cli2, "IDOR-99")
        db.session.commit()

        _login(client, "idor1@test.com")
        resp = _post_json(client, "/api/asistencia", {
            "descripcion": "Robo de vehiculo",
            "latitude": 4.71, "longitude": -74.07,
            "vehiculo_id": v_ajeno.id,
        })
        assert resp.status_code == 403
        # No se creo ninguna solicitud "limpia" que oculte el intento.
        assert AsistenciaEmergencia.query.count() == 0

    def test_vehiculo_ajeno_tampoco_via_ubicacion(self, client, db):
        cli1, _ = _crear_cliente_con_usuario(db, "Uno", "idor3")
        cli2, _ = _crear_cliente_con_usuario(db, "Dos", "idor4")
        v_ajeno = _crear_vehiculo(db, cli2, "IDOR-88")
        db.session.commit()
        _login(client, "idor3@test.com")
        resp = _post_json(client, "/api/ubicacion", {
            "latitude": 4.71, "longitude": -74.07, "vehiculo_id": v_ajeno.id,
        })
        assert resp.status_code == 403
        assert AsistenciaEmergencia.query.count() == 0

    def test_vehiculo_inexistente_es_rechazado(self, client, db):
        _crear_cliente_con_usuario(db, "Fantasma", "idor5")
        db.session.commit()
        _login(client, "idor5@test.com")
        resp = _post_json(client, "/api/asistencia", {
            "descripcion": "No existe",
            "latitude": 4.71, "longitude": -74.07,
            "vehiculo_id": 999999,
        })
        assert resp.status_code == 403
        assert AsistenciaEmergencia.query.count() == 0

    def test_no_puede_cancelar_asistencia_ajena(self, client, db):
        _crear_cliente_con_usuario(db, "Afectado", "idor6")
        _crear_cliente_con_usuario(db, "Victima", "idor7")
        _crear_staff(db, "idor6_staff")
        db.session.commit()

        _login(client, "idor7@test.com")
        r = _post_json(client, "/api/asistencia", {
            "descripcion": "Original", "latitude": 4.71, "longitude": -74.07,
        })
        aid = r.get_json()["id"]
        client.get("/auth/logout", follow_redirects=True)
        _login(client, "idor6@test.com")
        resp = _post_json(client, f"/api/asistencia/{aid}/cancelar", {})
        assert resp.status_code == 404
        assert db.session.get(AsistenciaEmergencia, aid).estado == "pendiente"

    def test_no_ve_asistencias_de_otros(self, client, db):
        _crear_cliente_con_usuario(db, "Ajeno", "idor8")
        _crear_cliente_con_usuario(db, "Dueño", "idor9")
        db.session.commit()
        _login(client, "idor9@test.com")
        _post_json(client, "/api/asistencia", {
            "descripcion": "Privada ajena", "latitude": 4.71, "longitude": -74.07,
        })
        client.get("/auth/logout", follow_redirects=True)
        _login(client, "idor8@test.com")
        assert client.get("/api/asistencia").get_json() == []

    def test_cliente_no_entra_al_panel_del_taller(self, client, db):
        _crear_cliente_con_usuario(db, "Curioso", "idor10")
        _crear_staff(db, "idor10_staff", "admin")
        db.session.commit()
        _login(client, "idor10@test.com")
        resp = client.get("/sedes/asistencias")
        # El panel es exclusivo del personal: el cliente es devuelto a su portal.
        assert resp.status_code == 302
        assert "/portal/" in resp.headers["Location"]
        assert b"Curioso" not in resp.data

    def test_notificaciones_son_por_usuario(self, client, db):
        _, u1 = _crear_cliente_con_usuario(db, "Uno", "idor11")
        _crear_cliente_con_usuario(db, "Dos", "idor12")
        n = NotificationService.notify(u1.id, "sistema", "Secreto de Uno")
        db.session.commit()
        _login(client, "idor12@test.com")
        resp = client.get("/notificaciones/api/listar")
        assert all(i["id"] != n.id for i in resp.get_json()["items"])
        assert client.post(f"/notificaciones/api/leer/{n.id}").status_code == 404
        # El intento ajeno no marca como leida la notificacion del otro usuario.
        assert db.session.get(Notificacion, n.id).leida is False


# --------------------------------------------------- contador y seguridad


class TestNotificacionesUi:
    def test_contador_reporta_total_real(self, client, db):
        _, u = _crear_cliente_con_usuario(db, "Contador", "cnt1")
        for i in range(3):
            NotificationService.notify(u.id, "sistema", f"N{i}")
        db.session.commit()
        _login(client, "cnt1@test.com")
        data = client.get("/notificaciones/api/listar").get_json()
        assert data["no_leidas"] == 3
        assert data["count"] == len(data["items"])

    def test_payload_expone_tipo_label_e_icono(self, client, db):
        _, u = _crear_cliente_con_usuario(db, "Icono", "cnt2")
        NotificationService.notify(u.id, "asistencia", "Asistencia", "Auxilio")
        db.session.commit()
        _login(client, "cnt2@test.com")
        item = client.get("/notificaciones/api/listar").get_json()["items"][0]
        assert item["tipo"] == "asistencia"
        assert item["tipo_label"] == "Asistencia"
        assert item["tipo_icon"] == "fa-truck-medical"

    def test_texto_se_escapa_en_la_pagina(self, client, db):
        _, u = _crear_cliente_con_usuario(db, "Escape", "cnt3")
        NotificationService.notify(u.id, "sistema", "<script>alert(1)</script>")
        db.session.commit()
        _login(client, "cnt3@test.com")
        resp = client.get("/notificaciones/")
        assert b"<script>alert(1)</script>" not in resp.data


# ---------------------------------------------------------- areas/roles


class TestIdentidadVisual:
    @pytest.mark.parametrize("rol", ["admin", "recepcion", "mecanico"])
    def test_staff_en_area_administrativa(self, client, db, rol):
        _crear_usuario(db, f"vis_{rol}@test.com", rol)
        db.session.commit()
        _login(client, f"vis_{rol}@test.com")
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", "ignore")
        assert "area-indicator-administrativa" in body
        assert "Área Administrativa" in body
        assert "area-indicator-portal_cliente" not in body

    def test_cliente_en_portal(self, client, db):
        _crear_cliente_con_usuario(db, "Cliente Visual", "vis_cli")
        db.session.commit()
        _login(client, "vis_cli@test.com")
        resp = client.get("/portal/")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", "ignore")
        assert "area-indicator-portal_cliente" in body
        assert "Portal del Cliente" in body
        assert "area-indicator-administrativa" not in body

    def test_rol_label_legible(self, db):
        assert _crear_usuario(db, "rl1@test.com", "admin").rol_label == "Administrador"
        assert _crear_usuario(db, "rl2@test.com", "mecanico").rol_label == "Personal de taller"
        assert _crear_usuario(db, "rl3@test.com", "cliente").rol_label == "Cliente"
        # Un rol desconocido no rompe la interfaz.
        assert _crear_usuario(db, "rl4@test.com", "inventado").rol_label

    def test_es_staff_es_fuente_unica(self, db):
        assert _crear_usuario(db, "st1@test.com", "admin").es_staff is True
        assert _crear_usuario(db, "st2@test.com", "recepcion").es_staff is True
        assert _crear_usuario(db, "st3@test.com", "mecanico").es_staff is True
        assert _crear_usuario(db, "st4@test.com", "cliente").es_staff is False

    def test_area_y_area_home_coherentes(self, db):
        admin = _crear_usuario(db, "ah1@test.com", "admin")
        cliente = _crear_usuario(db, "ah2@test.com", "cliente")
        assert admin.area == admin.AREA_ADMINISTRATIVA
        assert admin.area_home == "dashboard.index"
        assert cliente.area == cliente.AREA_PORTAL_CLIENTE
        assert cliente.area_home == "portal.index"


# -------------------------------------------------- selector de vehiculo


class TestSelectoresVehiculo:
    def test_portal_usa_mis_vehiculos(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Portal", "sel1")
        v = _crear_vehiculo(db, cli, "SEL-01")
        db.session.commit()
        _login(client, "sel1@test.com")
        resp = client.get("/portal/citas/solicitar")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", "ignore")
        # El selector identifica el vehiculo con datos reales, no solo la placa.
        assert v.placa in body
        assert "Chevrolet" in body and "2022" in body

    def test_sedes_muestra_selector_de_asistencia(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Sedes", "sel2")
        v = _crear_vehiculo(db, cli, "SEL-02")
        db.session.commit()
        _login(client, "sel2@test.com")
        resp = client.get("/sedes/")
        body = resp.data.decode("utf-8", "ignore")
        assert 'id="asistenciaVehiculo"' in body
        assert "/api/vehiculos/mios" in body

    def test_panel_taller_muestra_vehiculo(self, client, db):
        cli, _ = _crear_cliente_con_usuario(db, "Panel Veh", "sel3")
        v = _crear_vehiculo(db, cli, "SEL-03")
        _crear_staff(db, "sel3_staff")
        db.session.commit()

        # El cliente crea la solicitud...
        _login(client, "sel3@test.com")
        r = _post_json(client, "/api/asistencia", {
            "descripcion": "Con vehiculo",
            "latitude": 4.71, "longitude": -74.07, "vehiculo_id": v.id,
        })
        assert r.get_json()["success"] is True

        # ...y el taller la ve con la placa.
        client.get("/auth/logout", follow_redirects=True)
        _login(client, "sel3_staff@test.com")
        resp = client.get("/sedes/asistencias")
        assert v.placa in resp.data.decode("utf-8", "ignore")

    def test_asistente_se_presenta_como_virtual(self, client, db):
        _crear_usuario(db, "bot@test.com", "cliente", nombre="Curioso Bot")
        db.session.commit()
        _login(client, "bot@test.com")
        resp = client.get("/asistente/")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", "ignore")
        assert "virtual" in body.lower()
        # No se presenta como si hubiera una persona del taller respondiendo.
        assert "Online" not in body
