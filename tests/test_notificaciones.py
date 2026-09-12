"""FASE 9 y 14 - Notificaciones: modelo, servicio, API, página y flujos por rol."""
from datetime import date, time
from decimal import Decimal

from models import Usuario, Cliente, Vehiculo, Notificacion, Cita, OrdenTrabajo
from services.notification_service import NotificationService
from services.factura_service import FacturaService, FacturaInput
from services.recordatorio_service import RecordatorioService


def _crear_usuario(db, correo, rol, nombre="Usuario"):
    u = Usuario(nombre=nombre, correo=correo, rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.flush()
    return u


def _login(client, correo, password="clave1234"):
    return client.post("/auth/login", data={
        "correo": correo,
        "password": password,
    }, follow_redirects=True)


def _crear_cliente_con_usuario(db, nombre="Cliente Prueba"):
    cli = Cliente(nombre=nombre)
    db.session.add(cli)
    db.session.flush()
    u = _crear_usuario(db, "cliente_notif@test.com", "cliente", nombre=nombre)
    u.cliente_id = cli.id
    db.session.commit()
    return cli, u


class TestNotificationService:
    def test_notify_crea_y_consulta(self, db):
        u = _crear_usuario(db, "srv1@test.com", "cliente")
        db.session.commit()
        n = NotificationService.notify(
            u.id, "cita", "Título", "Mensaje", "/portal/citas"
        )
        assert n.id is not None
        assert n.tipo_label == "Cita"
        assert NotificationService.unread_count(u.id) == 1
        assert len(NotificationService.list_for(u.id)) == 1

    def test_mark_read_solo_dueño(self, db):
        u1 = _crear_usuario(db, "srv2@test.com", "cliente")
        u2 = _crear_usuario(db, "srv3@test.com", "cliente")
        db.session.commit()
        n = NotificationService.notify(u1.id, "sistema", "Privada")
        assert NotificationService.mark_read(u2.id, n.id) is False
        assert NotificationService.unread_count(u1.id) == 1
        assert NotificationService.mark_read(u1.id, n.id) is True
        assert NotificationService.unread_count(u1.id) == 0

    def test_mark_all_read(self, db):
        u = _crear_usuario(db, "srv4@test.com", "cliente")
        db.session.commit()
        NotificationService.notify(u.id, "sistema", "A")
        NotificationService.notify(u.id, "cita", "B")
        assert NotificationService.mark_all_read(u.id) == 2
        assert NotificationService.unread_count(u.id) == 0

    def test_notify_cliente_sin_cuenta_no_falla(self, db):
        cli = Cliente(nombre="Sin Usuario")
        db.session.add(cli)
        db.session.commit()
        result = NotificationService.notify_cliente(cli.id, "cita", "X")
        assert result is None

    def test_notify_roles(self, db):
        a = _crear_usuario(db, "rol1@test.com", "admin")
        r = _crear_usuario(db, "rol2@test.com", "recepcion")
        _crear_usuario(db, "rol3@test.com", "cliente")
        db.session.commit()
        creadas = NotificationService.notify_roles(
            ["admin", "recepcion"], "cita", "Nueva cita"
        )
        assert len(creadas) == 2
        assert NotificationService.unread_count(a.id) == 1
        assert NotificationService.unread_count(r.id) == 1

    def test_notify_staff(self, db):
        _crear_usuario(db, "st1@test.com", "admin")
        _crear_usuario(db, "st2@test.com", "mecanico")
        db.session.commit()
        creadas = NotificationService.notify_staff("orden", "OT creada")
        assert len(creadas) == 2


class TestNotificacionesApi:
    def test_api_requiere_login(self, client):
        resp = client.get("/notificaciones/api/listar")
        assert resp.status_code == 302

    def test_unread_count_cliente(self, client, db):
        cli, u = _crear_cliente_con_usuario(db)
        NotificationService.notify(u.id, "cita", "Hola")
        _login(client, "cliente_notif@test.com")
        assert NotificationService.unread_count(u.id) == 1

    def test_api_listar_y_leer(self, client, db):
        cli, u = _crear_cliente_con_usuario(db)
        NotificationService.notify(u.id, "cita", "Título", "Mensaje", "/portal/citas")
        _login(client, "cliente_notif@test.com")
        resp = client.get("/notificaciones/api/listar")
        assert resp.status_code == 200
        items = resp.get_json()["items"]
        assert len(items) == 1
        nid = items[0]["id"]
        resp = client.post(f"/notificaciones/api/leer/{nid}")
        assert resp.get_json()["success"] is True
        assert NotificationService.unread_count(u.id) == 0

    def test_api_leer_ajena_devuelve_404(self, client, db):
        cli1, u1 = _crear_cliente_con_usuario(db, "Cliente Uno")
        u2 = _crear_usuario(db, "otro@test.com", "cliente", nombre="Cliente Dos")
        db.session.commit()
        n = NotificationService.notify(u1.id, "sistema", "Privada")
        _login(client, "otro@test.com")
        resp = client.post(f"/notificaciones/api/leer/{n.id}")
        assert resp.status_code == 404
        assert not db.session.get(Notificacion, n.id).leida

    def test_api_leer_todas(self, client, db):
        cli, u = _crear_cliente_con_usuario(db)
        NotificationService.notify(u.id, "cita", "A")
        NotificationService.notify(u.id, "factura", "B")
        _login(client, "cliente_notif@test.com")
        resp = client.post("/notificaciones/api/leer-todas")
        assert resp.get_json()["marcadas"] == 2
        assert NotificationService.unread_count(u.id) == 0


class TestNotificacionModelo:
    def test_tabla_registrada_en_metadata(self, app):
        from database.db import db
        assert "notificaciones" in db.metadata.tables


def _crear_cliente_vehiculo(db, placa="NOT-123", nombre="Cliente Rol"):
    cli = Cliente(nombre=nombre)
    db.session.add(cli)
    db.session.flush()
    u = _crear_usuario(db, f"rol_{placa.lower()}@test.com", "cliente", nombre=nombre)
    u.cliente_id = cli.id
    v = Vehiculo(cliente_id=cli.id, marca="Chevrolet", modelo="Spark", placa=placa)
    db.session.add(v)
    db.session.flush()
    return cli, u, v


def _crear_ot(db, cli, v, numero="OT-NOTIF-1"):
    ot = OrdenTrabajo(numero=numero, cliente_id=cli.id, vehiculo_id=v.id,
                      diagnostico_inicial="Revisión general")
    db.session.add(ot)
    db.session.commit()
    return ot


def _crear_factura(db, cli, v):
    cita = Cita(cliente_id=cli.id, vehiculo_id=v.id, fecha=date.today(), hora=time(10, 0))
    db.session.add(cita)
    db.session.commit()
    from models import Servicio
    s = Servicio(nombre="Cambio de aceite", precio_estimado=50000)
    db.session.add(s)
    db.session.commit()
    factura = FacturaService.generar(FacturaInput(
        cita_id=cita.id, servicio_ids=[s.id], precios=[Decimal("50000")],
        cantidades=[1], descuento=Decimal("0"), metodo_pago="Efectivo",
    ))
    return cita, factura


class TestFlujosRoleados:
    def test_ot_listo_entrega_notifica_cliente(self, client, db):
        admin = _crear_usuario(db, "ot_admin@test.com", "admin")
        db.session.commit()
        cli, u, v = _crear_cliente_vehiculo(db)
        db.session.commit()
        ot = _crear_ot(db, cli, v)
        _login(client, "ot_admin@test.com")
        resp = client.post(f"/ordenes-trabajo/cambiar-estado/{ot.id}",
                           data={"estado": "listo_entrega", "csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert any(n.tipo == "orden" for n in NotificationService.list_for(u.id))

    def test_ot_asignada_notifica_mecanicos(self, client, db):
        _crear_usuario(db, "mec_role@test.com", "mecanico")
        admin = _crear_usuario(db, "ot_admin2@test.com", "admin")
        db.session.commit()
        cli, u, v = _crear_cliente_vehiculo(db, placa="MEC-001")
        db.session.commit()
        from models.mecanico import Mecanico
        mec = Mecanico(nombre="Mecánico Uno", activo=True)
        db.session.add(mec)
        db.session.commit()
        _login(client, "ot_admin2@test.com")
        resp = client.post("/ordenes-trabajo/crear", data={
            "cliente_id": cli.id, "vehiculo_id": v.id, "mecanico_id": mec.id,
            "fecha_ingreso": "2026-08-14", "diagnostico_inicial": "Afinación",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        mec_user = Usuario.query.filter_by(correo="mec_role@test.com").first()
        assert NotificationService.unread_count(mec_user.id) >= 1

    def test_factura_pagada_notifica_cliente(self, client, db):
        admin = _crear_usuario(db, "pago_admin@test.com", "admin")
        db.session.commit()
        cli, u, v = _crear_cliente_vehiculo(db, placa="PAG-001")
        db.session.commit()
        cita, factura = _crear_factura(db, cli, v)
        _login(client, "pago_admin@test.com")
        resp = client.post(f"/facturas/pagar/{factura.id}", data={
            "monto": "59500", "metodo_pago": "Efectivo", "referencia": "",
            "notas": "", "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert any(n.tipo == "pago" for n in NotificationService.list_for(u.id))

    def test_cita_completada_notifica_cliente(self, client, db):
        admin = _crear_usuario(db, "cita_admin@test.com", "admin")
        db.session.commit()
        cli, u, v = _crear_cliente_vehiculo(db, placa="CIT-001")
        db.session.commit()
        cita = Cita(cliente_id=cli.id, vehiculo_id=v.id, fecha=date.today(),
                    hora=time(11, 0), descripcion="Afinación")
        db.session.add(cita)
        db.session.commit()
        _login(client, "cita_admin@test.com")
        resp = client.post(f"/citas/cambiar-estado/{cita.id}/completado",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert resp.status_code == 200
        assert any(n.tipo == "cita" for n in NotificationService.list_for(u.id))

    def test_garantia_creada_notifica_cliente(self, client, db):
        admin = _crear_usuario(db, "gar_admin@test.com", "admin")
        db.session.commit()
        cli, u, v = _crear_cliente_vehiculo(db, placa="GAR-001")
        db.session.commit()
        _login(client, "gar_admin@test.com")
        resp = client.post("/garantias/crear", data={
            "cliente_id": cli.id, "vehiculo_id": v.id, "descripcion": "Garantía motor",
            "meses_validez": "3", "servicio_id": "0", "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert any(n.tipo == "garantia" for n in NotificationService.list_for(u.id))

    def test_garantia_reclamada_notifica_staff(self, client, db):
        admin = _crear_usuario(db, "recl_admin@test.com", "admin")
        db.session.commit()
        cli, u, v = _crear_cliente_vehiculo(db, placa="REC-001")
        db.session.commit()
        from models.garantia import Garantia
        g = Garantia(codigo="GAR-REC-1", cliente_id=cli.id, vehiculo_id=v.id,
                     descripcion="Frenos", meses_validez=3, fecha_inicio=date.today(),
                     fecha_fin=date(2026, 11, 14))
        db.session.add(g)
        db.session.commit()
        _login(client, "recl_admin@test.com")
        resp = client.post(f"/garantias/cambiar-estado/{g.id}/reclamada",
                           data={"nota": "Ruido al frenar"}, follow_redirects=True)
        assert resp.status_code == 200
        assert any(n.tipo == "garantia" for n in NotificationService.list_for(admin.id))

    def test_recordatorio_creado_notifica_cliente(self, db):
        cli, u, v = _crear_cliente_vehiculo(db, placa="REC-D-1")
        db.session.commit()
        RecordatorioService.crear_manual(v.id, "Cambio de aceite", "Próximo",
                                         date.today())
        assert any(n.tipo == "recordatorio" for n in NotificationService.list_for(u.id))

    def test_cliente_cancela_cita_notifica_staff(self, client, db):
        admin = _crear_usuario(db, "canc_admin@test.com", "admin")
        cli, u, v = _crear_cliente_vehiculo(db, placa="CAN-001")
        cita = Cita(cliente_id=cli.id, vehiculo_id=v.id, fecha=date(2026, 9, 1),
                    hora=time(9, 0), estado="pendiente")
        db.session.add(cita)
        db.session.commit()
        _login(client, "rol_can-001@test.com")
        resp = client.post(f"/portal/citas/{cita.id}/cancelar", follow_redirects=True)
        assert resp.status_code == 200
        assert any(n.tipo == "cita" for n in NotificationService.list_for(admin.id))


class TestPaginaNotificaciones:
    def test_pagina_requiere_login(self, client):
        resp = client.get("/notificaciones/", follow_redirects=True)
        assert resp.status_code == 200

    def test_pagina_muestra_items(self, client, db):
        cli, u = _crear_cliente_con_usuario(db)
        NotificationService.notify(u.id, "cita", "Hola cliente")
        _login(client, "cliente_notif@test.com")
        resp = client.get("/notificaciones/")
        assert resp.status_code == 200
        assert b"Hola cliente" in resp.data

    def test_filtro_por_tipo(self, client, db):
        cli, u = _crear_cliente_con_usuario(db)
        NotificationService.notify(u.id, "cita", "De cita")
        NotificationService.notify(u.id, "factura", "De factura")
        _login(client, "cliente_notif@test.com")
        resp = client.get("/notificaciones/?tipo=factura")
        assert b"De factura" in resp.data
        assert b"De cita" not in resp.data

    def test_eliminar_propia(self, client, db):
        cli, u = _crear_cliente_con_usuario(db)
        n = NotificationService.notify(u.id, "cita", "Borrame")
        _login(client, "cliente_notif@test.com")
        resp = client.post(f"/notificaciones/eliminar/{n.id}",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert resp.status_code == 200
        assert db.session.get(Notificacion, n.id) is None

    def test_eliminar_ajena_protege_idor(self, client, db):
        cli1, u1 = _crear_cliente_con_usuario(db, "Dueño")
        u2 = _crear_usuario(db, "intruso@test.com", "cliente", nombre="Intruso")
        db.session.commit()
        n = NotificationService.notify(u1.id, "sistema", "Privada")
        _login(client, "intruso@test.com")
        resp = client.post(f"/notificaciones/eliminar/{n.id}",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert db.session.get(Notificacion, n.id) is not None
