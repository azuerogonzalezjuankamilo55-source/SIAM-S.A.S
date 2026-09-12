"""FASE 3 - Sedes en base de datos y citas con sede/servicio + validaciÃ³n de horarios."""
from datetime import date, time

from models import Usuario, Cliente, Vehiculo, Cita
from services.sede_service import SedeService


def _crear_cliente(db, correo="cli_sede@test.com"):
    c = Cliente(nombre="Cliente Sede", correo=correo, telefono="3000000001")
    db.session.add(c)
    db.session.commit()
    u = Usuario(nombre="Cliente Sede", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return c, u


def _login(client, correo, password="clave1234"):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


def _crear_staff(db, correo="mecanico@test.com", rol="mecanico"):
    u = Usuario(nombre=rol, correo=correo, rol=rol)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


class TestSedeService:
    def test_seed_inserta_sedes_por_defecto(self, app, db):
        with app.app_context():
            SedeService.seed_sedes()
            sedes = SedeService.listar()
            assert len(sedes) == 4
            nombres = {s["nombre"] for s in sedes}
            assert "Sede Principal Soacha" in nombres
            assert "Sede Norte Bogotá" in nombres

    def test_seed_es_idempotente(self, app, db):
        with app.app_context():
            SedeService.seed_sedes()
            SedeService.seed_sedes()
            assert len(SedeService.listar()) == 4

    def test_to_dict_tiene_claves_completas(self, app, db):
        with app.app_context():
            SedeService.seed_sedes()
            s = SedeService.listar()[0]
            for key in ("id", "nombre", "direccion", "telefono", "horario", "latitud", "longitud", "servicios"):
                assert key in s
            assert isinstance(s["servicios"], list) and s["servicios"]

    def test_sede_ocupada_detecta_cruce(self, app, db):
        from models import Sede
        with app.app_context():
            SedeService.seed_sedes()
            sede_id = Sede.query.first().id
            c, u = _crear_cliente(db, correo="ocu@test.com")
            v = Vehiculo(placa="O1", marca="A", modelo="B", cliente_id=c.id)
            db.session.add(v)
            db.session.commit()
            db.session.add(Cita(
                cliente_id=c.id, vehiculo_id=v.id, sede_id=sede_id,
                fecha=date(2026, 9, 1), hora=time(10, 0), estado="pendiente",
            ))
            db.session.commit()
            assert SedeService.sede_ocupada(sede_id, date(2026, 9, 1), time(10, 0)) is True
            assert SedeService.sede_ocupada(sede_id, date(2026, 9, 1), time(11, 0)) is False
            assert SedeService.sede_ocupada(sede_id, date(2026, 9, 2), time(10, 0)) is False

    def test_sede_ocupada_ignora_canceladas(self, app, db):
        from models import Sede
        with app.app_context():
            SedeService.seed_sedes()
            sede_id = Sede.query.first().id
            c, u = _crear_cliente(db, correo="can@test.com")
            v = Vehiculo(placa="O2", marca="A", modelo="B", cliente_id=c.id)
            db.session.add(v)
            db.session.commit()
            db.session.add(Cita(
                cliente_id=c.id, vehiculo_id=v.id, sede_id=sede_id,
                fecha=date(2026, 9, 1), hora=time(10, 0), estado="cancelado",
            ))
            db.session.commit()
            assert SedeService.sede_ocupada(sede_id, date(2026, 9, 1), time(10, 0)) is False


class TestPaginaSedes:
    def test_pagina_publica(self, client):
        resp = client.get("/sedes/")
        assert resp.status_code == 200
        assert b"Sede" in resp.data

    def test_api_devuelve_sedes(self, client):
        resp = client.get("/sedes/api")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 4
        assert data[0]["servicios"]

    def test_api_compatible_con_publico(self, client):
        resp = client.get("/sedes/api")
        data = resp.get_json()
        assert {"id", "nombre", "latitud", "longitud"} <= set(data[0].keys())


class TestCitaConSedePortal:
    def _preparar(self, db, correo="sede@test.com"):
        c, u = _crear_cliente(db, correo=correo)
        v = Vehiculo(placa="S1", marca="Toyota", modelo="Corolla", cliente_id=c.id)
        db.session.add(v)
        db.session.commit()
        return c, u, v

    def test_solicitar_guarda_sede(self, client, db):
        c, u, v = self._preparar(db)
        _login(client, u.correo)
        resp = client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 1,
            "fecha": "2026-09-01",
            "hora": "10:00",
            "descripcion": "Freno",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cita = Cita.query.filter_by(cliente_id=c.id).first()
        assert cita is not None
        assert cita.sede_id == 1

    def test_solicitar_rechaza_horario_ocupado(self, client, db):
        c, u, v = self._preparar(db, correo="dup@test.com")
        _login(client, u.correo)
        client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 1,
            "fecha": "2026-09-01",
            "hora": "10:00",
        }, follow_redirects=True)
        resp2 = client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 1,
            "fecha": "2026-09-01",
            "hora": "10:00",
        }, follow_redirects=True)
        assert b"reservado" in resp2.data
        assert Cita.query.filter_by(cliente_id=c.id).count() == 1

    def test_solicitar_permite_hora_distinta(self, client, db):
        c, u, v = self._preparar(db, correo="libre@test.com")
        _login(client, u.correo)
        client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 1,
            "fecha": "2026-09-01",
            "hora": "10:00",
        }, follow_redirects=True)
        client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 1,
            "fecha": "2026-09-01",
            "hora": "11:00",
        }, follow_redirects=True)
        assert Cita.query.filter_by(cliente_id=c.id).count() == 2

    def test_solicitar_rechaza_sede_invalida(self, client, db):
        c, u, v = self._preparar(db, correo="inv@test.com")
        _login(client, u.correo)
        resp = client.post("/portal/citas/solicitar", data={
            "vehiculo_id": v.id,
            "sede_id": 999,
            "fecha": "2026-09-01",
            "hora": "10:00",
        }, follow_redirects=True)
        assert b"Sede inv" in resp.data or b"Sede" in resp.data
        assert Cita.query.filter_by(cliente_id=c.id).count() == 0


class TestCitaConSedeStaff:
    def test_crear_guarda_sede_y_servicio(self, client, db):
        from models import Servicio
        _crear_staff(db)
        _crear_staff(db, correo="recepcion@test.com", rol="recepcion")
        c = Cliente(nombre="Cli", correo="cc@test.com")
        db.session.add(c)
        db.session.commit()
        v = Vehiculo(placa="T1", marca="M", modelo="Y", cliente_id=c.id)
        db.session.add(v)
        sv = Servicio(nombre="Cambio de aceite", precio_estimado=50000)
        db.session.add(sv)
        db.session.commit()
        _login(client, "recepcion@test.com")
        resp = client.post("/citas/crear", data={
            "cliente_id": c.id,
            "vehiculo_id": v.id,
            "sede_id": 1,
            "servicio_id": sv.id,
            "fecha": "2026-09-02",
            "hora": "09:00",
        }, follow_redirects=True)
        assert resp.status_code == 200
        cita = Cita.query.filter_by(cliente_id=c.id).first()
        assert cita is not None
        assert cita.sede_id == 1
        assert cita.servicio_id == sv.id



