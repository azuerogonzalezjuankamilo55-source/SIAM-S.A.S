import pytest
from datetime import date, timedelta

from models import Usuario, Cliente, Vehiculo
from models.historial_vehiculo import HistorialVehiculo
from models.recordatorio import Recordatorio
from services.recordatorio_service import RecordatorioService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_rec@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_cliente(db, correo="cliente_rec@test.com"):
    c = Cliente(nombre="Cliente Rec", correo=correo, telefono="3009876543")
    db.session.add(c)
    db.session.commit()
    u = Usuario(nombre="Cliente Rec", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return c, u


def _crear_vehiculo(db, placa="REC-001", cliente_id=None):
    if not cliente_id:
        c = Cliente(nombre="Cliente Rec", correo=f"{placa.lower()}@test.com")
        db.session.add(c)
        db.session.commit()
        cliente_id = c.id
    v = Vehiculo(cliente_id=cliente_id, marca="Toyota", modelo="Corolla", placa=placa)
    db.session.add(v)
    db.session.commit()
    return v


def _aceite_antiguo(db, vehiculo, dias=240):
    db.session.add(HistorialVehiculo(
        vehiculo_id=vehiculo.id, tipo="cambio_aceite", descripcion="Cambio",
        fecha=date.today() - timedelta(days=dias),
    ))
    db.session.commit()


def _login(client, correo, password):
    return client.post("/auth/login", data={"correo": correo, "password": password},
                       follow_redirects=True)


class TestGenerar:
    def test_sin_vehiculos_no_genera(self, db):
        assert RecordatorioService.generar_mantenimientos() == 0

    def test_aceite_vencido_genera(self, db):
        v = _crear_vehiculo(db)
        _aceite_antiguo(db, v)
        creados = RecordatorioService.generar_mantenimientos()
        assert creados == 1
        rec = Recordatorio.query.first()
        assert rec.servicio_mantenimiento == "aceite"
        assert rec.titulo.startswith("Cambio de aceite")
        assert rec.estado == "pendiente"

    def test_no_duplica(self, db):
        v = _crear_vehiculo(db)
        _aceite_antiguo(db, v)
        assert RecordatorioService.generar_mantenimientos() == 1
        assert RecordatorioService.generar_mantenimientos() == 0
        assert Recordatorio.query.count() == 1

    def test_aceite_al_dia_no_genera(self, db):
        v = _crear_vehiculo(db)
        _aceite_antiguo(db, v, dias=60)
        assert RecordatorioService.generar_mantenimientos() == 0


class TestManual:
    def test_crear_manual(self, db):
        v = _crear_vehiculo(db)
        rec = RecordatorioService.crear_manual(
            v.id, "Cambio de pastillas", "Pastillas delanteras",
            date.today() + timedelta(days=7),
        )
        assert rec.tipo == "manual"
        assert rec.estado == "pendiente"
        assert rec.canal == "portal"
        assert Recordatorio.query.count() == 1

    def test_crear_manual_vehiculo_inexistente(self, db):
        with pytest.raises(ValueError):
            RecordatorioService.crear_manual(9999, "X", None, date.today())


class TestEstados:
    def test_cambiar_estado(self, db):
        v = _crear_vehiculo(db)
        rec = RecordatorioService.crear_manual(v.id, "Aviso", None, date.today())
        RecordatorioService.cambiar_estado(rec.id, "enviado")
        rec = db.session.get(Recordatorio, rec.id)
        assert rec.estado == "enviado"
        assert rec.enviado_at is not None
        RecordatorioService.cambiar_estado(rec.id, "completado")
        rec = db.session.get(Recordatorio, rec.id)
        assert rec.estado == "completado"
        assert rec.completado_at is not None

    def test_estado_invalido(self, db):
        v = _crear_vehiculo(db)
        rec = RecordatorioService.crear_manual(v.id, "Aviso", None, date.today())
        with pytest.raises(ValueError):
            RecordatorioService.cambiar_estado(rec.id, "inexistente")

    def test_estado_no_existe(self, db):
        assert RecordatorioService.cambiar_estado(9999, "enviado") is None


class TestConsultas:
    def test_get_todos_filtros(self, db):
        v = _crear_vehiculo(db)
        RecordatorioService.crear_manual(v.id, "Aviso 1", None, date.today())
        RecordatorioService.crear_manual(v.id, "Aviso 2", None, date.today(), canal="correo")
        todos = RecordatorioService.get_todos()
        assert len(todos) == 2
        assert len(RecordatorioService.get_todos(estado="pendiente")) == 2
        assert len(RecordatorioService.get_todos(tipo="manual")) == 2
        assert len(RecordatorioService.get_todos(estado="enviado")) == 0

    def test_get_para_cliente(self, db):
        c1, _ = _crear_cliente(db, correo="c1_rec@test.com")
        v1 = _crear_vehiculo(db, placa="REC-001", cliente_id=c1.id)
        RecordatorioService.crear_manual(v1.id, "Aviso propio", None, date.today())

        c2 = Cliente(nombre="Otro", correo="c2_rec@test.com")
        db.session.add(c2)
        db.session.commit()
        v2 = Vehiculo(cliente_id=c2.id, marca="Mazda", modelo="3", placa="REC-002")
        db.session.add(v2)
        db.session.commit()
        RecordatorioService.crear_manual(v2.id, "Aviso ajeno", None, date.today())

        lista = RecordatorioService.get_para_cliente(c1)
        assert len(lista) == 1
        assert lista[0].titulo == "Aviso propio"


class TestRoutes:
    def test_index_requiere_admin(self, client, db):
        resp = client.get("/recordatorios/", follow_redirects=True)
        assert resp.status_code == 200

    def test_index_admin(self, client, db):
        _crear_admin(db)
        _login(client, "admin_rec@test.com", "admin123")
        resp = client.get("/recordatorios/")
        assert resp.status_code == 200
        assert "Recordatorios" in resp.data.decode("utf-8")

    def test_cliente_no_ve_recordatorios_admin(self, client, db):
        _crear_cliente(db)
        _login(client, "cliente_rec@test.com", "clave1234")
        resp = client.get("/recordatorios/", follow_redirects=True)
        assert resp.status_code == 200
        assert "No tienes permisos de administrador" in resp.data.decode("utf-8")

    def test_generar_route(self, client, db):
        _crear_admin(db)
        _login(client, "admin_rec@test.com", "admin123")
        v = _crear_vehiculo(db)
        _aceite_antiguo(db, v)
        resp = client.post("/recordatorios/generar", data={"csrf_token": "x"},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert Recordatorio.query.count() == 1
        assert "generaron 1" in resp.data.decode("utf-8")

    def test_crear_route(self, client, db):
        _crear_admin(db)
        _login(client, "admin_rec@test.com", "admin123")
        v = _crear_vehiculo(db)
        resp = client.post("/recordatorios/crear", data={
            "vehiculo_id": str(v.id),
            "titulo": "Cambio de frenos",
            "descripcion": "Freno trasero",
            "fecha_programada": (date.today() + timedelta(days=5)).isoformat(),
            "canal": "whatsapp",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        rec = Recordatorio.query.first()
        assert rec is not None
        assert rec.titulo == "Cambio de frenos"
        assert rec.canal == "whatsapp"

    def test_cambiar_estado_route(self, client, db):
        _crear_admin(db)
        _login(client, "admin_rec@test.com", "admin123")
        v = _crear_vehiculo(db)
        rec = RecordatorioService.crear_manual(v.id, "Aviso", None, date.today())
        resp = client.post(f"/recordatorios/{rec.id}/estado/enviado",
                           data={"csrf_token": "x"}, follow_redirects=True)
        assert resp.status_code == 200
        rec = db.session.get(Recordatorio, rec.id)
        assert rec.estado == "enviado"

    def test_portal_recordatorios(self, client, db):
        c, u = _crear_cliente(db)
        v = _crear_vehiculo(db, placa="REC-P1", cliente_id=c.id)
        RecordatorioService.crear_manual(v.id, "Cambio de aceite", None,
                                         date.today() + timedelta(days=3))
        _login(client, u.correo, "clave1234")
        resp = client.get("/portal/recordatorios")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Cambio de aceite" in html
        assert "Agendar cita" in html
