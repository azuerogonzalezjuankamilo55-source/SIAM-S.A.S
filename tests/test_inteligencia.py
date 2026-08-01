import pytest
from datetime import date, timedelta

from models import Usuario, Cliente, Vehiculo
from models.historial_vehiculo import HistorialVehiculo
from services.inteligencia_service import InteligenciaService


def _crear_admin(db):
    u = Usuario(nombre="Admin", correo="admin_ia@test.com", rol="admin")
    u.set_password("admin123")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_vehiculo(db, placa="IA-001"):
    c = Cliente(nombre="Cliente IA", correo="ia@test.com")
    db.session.add(c)
    db.session.commit()
    v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa=placa)
    db.session.add(v)
    db.session.commit()
    return v


def _login(client):
    return client.post("/auth/login", data={"correo": "admin_ia@test.com", "password": "admin123"},
                       follow_redirects=True)


class TestDiagnostico:
    def test_ruido_motor(self, db):
        res = InteligenciaService.diagnosticar(None, "El motor hace un ruido raro")
        assert res["sintomas"] != []
        assert res["causas"] != []
        assert res["urgencia"] == "media"

    def test_frenos_prioridad_alta(self, db):
        res = InteligenciaService.diagnosticar(None, "chillido al frenar, vibra el pedal")
        assert res["urgencia"] == "alta"

    def test_sintoma_vacio(self, db):
        res = InteligenciaService.diagnosticar(None, "  ")
        assert res["causas"] == []
        assert "consejo" in res

    def test_sintoma_no_reconocido(self, db):
        res = InteligenciaService.diagnosticar(None, "mi carro hace zzz")
        assert res["sintomas"] == []

    def test_con_vehiculo(self, db):
        v = _crear_vehiculo(db)
        res = InteligenciaService.diagnosticar(v.id, "no prende")
        assert res["vehiculo"]["placa"] == "IA-001"
        assert res["urgencia"] == "alta"


class TestRecomendaciones:
    def test_sin_historial_sin_dato(self, db):
        v = _crear_vehiculo(db)
        datos = InteligenciaService.recomendar_mantenimiento(v.id)
        estados = {r["estado"] for r in datos["recomendaciones"]}
        assert "sin_dato" in estados

    def test_aceite_reciente_al_dia(self, db):
        v = _crear_vehiculo(db)
        db.session.add(HistorialVehiculo(
            vehiculo_id=v.id, tipo="cambio_aceite", descripcion="Cambio",
            fecha=date.today() - timedelta(days=60),
        ))
        db.session.commit()
        datos = InteligenciaService.recomendar_mantenimiento(v.id)
        aceite = next(r for r in datos["recomendaciones"] if r["nombre"].startswith("Cambio de aceite"))
        assert aceite["estado"] == "al_dia"

    def test_aceite_vencido(self, db):
        v = _crear_vehiculo(db)
        db.session.add(HistorialVehiculo(
            vehiculo_id=v.id, tipo="cambio_aceite", descripcion="Cambio",
            fecha=date.today() - timedelta(days=240),
        ))
        db.session.commit()
        datos = InteligenciaService.recomendar_mantenimiento(v.id)
        aceite = next(r for r in datos["recomendaciones"] if r["nombre"].startswith("Cambio de aceite"))
        assert aceite["estado"] == "vencido"

    def test_resumen_taller(self, db):
        resumen = InteligenciaService.resumen_taller()
        assert isinstance(resumen, str)
        assert len(resumen) > 0


class TestRoutes:
    def test_ia_requiere_login(self, client):
        resp = client.get("/ia/", follow_redirects=True)
        assert resp.status_code == 200

    def test_ia_index(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.get("/ia/")
        assert resp.status_code == 200
        assert b"Diagn" in resp.data or "Diagn" in resp.data.decode("utf-8")

    def test_diagnosticar_post(self, client, db):
        _crear_admin(db)
        _login(client)
        resp = client.post("/ia/diagnosticar", data={
            "vehiculo_id": "",
            "sintomas": "vibra al frenar",
            "csrf_token": "x",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Pastillas" in resp.data or "Pastillas" in resp.data.decode("utf-8")

    def test_mantenimiento_route(self, client, db):
        _crear_admin(db)
        v = _crear_vehiculo(db)
        _login(client)
        resp = client.get(f"/ia/mantenimiento/{v.id}")
        assert resp.status_code == 200
        assert b"Cambio de aceite" in resp.data
