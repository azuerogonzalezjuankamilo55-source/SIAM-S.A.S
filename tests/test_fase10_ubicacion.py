"""FASE 10 - Geolocalización de clientes en camino (UbicacionesCliente).

Cubre: modelo, /api/ubicacion/actualizar, /api/ubicacion/detener,
/api/ubicacion/estado y /api/admin/clientes-en-camino.
"""
from datetime import date, time

from models import Cliente, Usuario, Vehiculo, Cita, UbicacionCliente

COORDS = {"latitude": 4.62, "longitude": -74.12, "accuracy": 20.0}


def _crear_cliente(db, correo="cli_ubicacion@test.com", placa="UBI-001", estado="confirmada"):
    c = Cliente(nombre="Cliente Ubicacion", correo=correo, telefono="3001234567")
    db.session.add(c)
    db.session.flush()
    u = Usuario(nombre="Cliente Ubicacion", correo=correo, rol="cliente", cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa=placa)
    db.session.add(v)
    db.session.flush()
    cita = Cita(
        cliente_id=c.id, vehiculo_id=v.id,
        fecha=date.today(), hora=time(10, 0), estado=estado,
    )
    db.session.add(cita)
    db.session.commit()
    return c, u, v, cita


def _crear_admin(db, correo="admin_ubicacion@test.com"):
    u = Usuario(nombre="Admin Ubicacion", correo=correo, rol="admin")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo="cli_ubicacion@test.com", clave="clave1234"):
    return client.post("/auth/login", data={"correo": correo, "password": clave},
                       follow_redirects=True)


def _logout(client):
    return client.get("/auth/logout")


class TestModeloUbicacionCliente:

    def test_persiste_ubicacion(self, db):
        c = Cliente(nombre="X")
        db.session.add(c)
        db.session.flush()
        r = UbicacionCliente(cliente_id=c.id, latitude=4.6, longitude=-74.1, accuracy=10.0)
        db.session.add(r)
        db.session.commit()
        row = db.session.get(UbicacionCliente, r.id)
        assert row is not None
        assert row.cliente_id == c.id
        assert row.latitude == 4.6
        assert row.sharing_active is True
        assert row.accuracy == 10.0


class TestActualizarUbicacion:

    def test_requiere_login(self, client):
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code in (401, 302)

    def test_usuario_sin_cliente_rechazado(self, client, db):
        u = Usuario(nombre="Sin Cliente", correo="sincliente@test.com", rol="cliente")
        u.set_password("clave1234")
        db.session.add(u)
        db.session.commit()
        _login(client, correo="sincliente@test.com")
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code == 403
        assert r.get_json()["success"] is False

    def test_actualiza_con_cita_activa(self, client, db):
        c, _, _, cita = _crear_cliente(db)
        _login(client)
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["cita_id"] == cita.id
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id, cita_id=cita.id).first()
        assert reg is not None
        assert reg.latitude == 4.62
        assert reg.longitude == -74.12
        assert reg.accuracy == 20.0
        assert reg.sharing_active is True

    def test_no_duplica_registro(self, client, db):
        c, _, _, _ = _crear_cliente(db)
        _login(client)
        for _ in range(3):
            client.post("/api/ubicacion/actualizar", json=COORDS)
        assert UbicacionCliente.query.filter_by(cliente_id=c.id).count() == 1

    def test_sin_cita_activa_rechazado(self, client, db):
        _crear_cliente(db, estado="entregada")
        _login(client)
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code == 400
        assert r.get_json()["success"] is False

    def test_estados_activos_y_no_activos(self, client, db):
        for estado, esperado in [
            ("pendiente", 200), ("confirmada", 200), ("en_revision", 200),
            ("en_reparacion", 200), ("lista", 200),
            ("entregada", 400), ("cancelado", 400),
        ]:
            correo = f"uc_{estado}@test.com"
            _crear_cliente(db, correo=correo, placa=f"UC-{estado[:3]}-{estado[4:6]}", estado=estado)
            _login(client, correo=correo)
            r = client.post("/api/ubicacion/actualizar", json=COORDS)
            assert r.status_code == esperado, f"estado={estado} -> {r.status_code}"
            _logout(client)

    def test_coordenadas_invalidas(self, client, db):
        _crear_cliente(db)
        _login(client)
        r = client.post("/api/ubicacion/actualizar", json={"latitude": 999, "longitude": -74.1})
        assert r.status_code == 400
        r2 = client.post("/api/ubicacion/actualizar", json={"latitude": "abc", "longitude": -74.1})
        assert r2.status_code == 400

    def test_cita_ajena_rechazada(self, client, db):
        cita1 = _crear_cliente(db, correo="a@test.com", placa="AAA-111")[3]
        _crear_cliente(db, correo="b@test.com", placa="BBB-222")
        _login(client, correo="b@test.com")
        r = client.post("/api/ubicacion/actualizar", json={**COORDS, "cita_id": cita1.id})
        assert r.status_code == 400


class TestDetenerUbicacion:

    def test_detener_apaga_compartido(self, client, db):
        c, _, _, cita = _crear_cliente(db)
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        r = client.post("/api/ubicacion/detener", json={"cita_id": cita.id})
        assert r.status_code == 200
        assert r.get_json()["success"] is True
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id).first()
        assert reg.sharing_active is False

    def test_detener_sin_cita(self, client, db):
        c, _, _, _ = _crear_cliente(db)
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        r = client.post("/api/ubicacion/detener", json={})
        assert r.status_code == 200
        assert r.get_json()["apagadas"] == 1

    def test_detener_requiere_login(self, client):
        r = client.post("/api/ubicacion/detener", json={})
        assert r.status_code in (401, 302)


class TestEstadoUbicacion:

    def test_estado_sin_cita_activa(self, client, db):
        _crear_cliente(db, estado="cancelado")
        _login(client)
        r = client.get("/api/ubicacion/estado")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["tiene_cita_activa"] is False
        assert data["compartiendo"] is False
        assert data["taller"]["latitude"] is not None

    def test_estado_con_cita_activa(self, client, db):
        _, _, _, cita = _crear_cliente(db)
        _login(client)
        r = client.get("/api/ubicacion/estado")
        data = r.get_json()
        assert data["tiene_cita_activa"] is True
        assert data["cita"]["id"] == cita.id
        assert data["compartiendo"] is False


class TestClientesEnCamino:

    def test_requiere_staff(self, client, db):
        _crear_cliente(db)
        _login(client)
        r = client.get("/api/admin/clientes-en-camino")
        assert r.status_code in (302, 403)

    def test_lista_clientes_compartiendo(self, client, db):
        c, _, v, cita = _crear_cliente(db)
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        _logout(client)

        _crear_admin(db)
        _login(client, correo="admin_ubicacion@test.com")
        r = client.get("/api/admin/clientes-en-camino")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["taller"] is not None
        clientes = data["clientes"]
        assert len(clientes) == 1
        c1 = clientes[0]
        assert c1["cliente_id"] == c.id
        assert c1["cliente_nombre"] == "Cliente Ubicacion"
        assert c1["vehiculo_marca"] == "Toyota"
        assert c1["vehiculo_placa"] == "UBI-001"
        assert c1["cita_id"] == cita.id
        assert c1["latitude"] == 4.62
        assert c1["longitude"] == -74.12

    def test_no_aparecen_citas_finalizadas(self, client, db):
        _crear_cliente(db, estado="entregada")
        _login(client)
        r = client.post("/api/ubicacion/actualizar", json=COORDS)
        assert r.status_code == 400
        _logout(client)

        _crear_admin(db)
        _login(client, correo="admin_ubicacion@test.com")
        r = client.get("/api/admin/clientes-en-camino")
        data = r.get_json()
        assert len(data["clientes"]) == 0

    def test_detener_quita_del_listado(self, client, db):
        c, _, _, _ = _crear_cliente(db)
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        client.post("/api/ubicacion/detener", json={})
        _logout(client)

        _crear_admin(db)
        _login(client, correo="admin_ubicacion@test.com")
        r = client.get("/api/admin/clientes-en-camino")
        assert r.get_json()["clientes"] == []

    def test_servicio_asociado_se_incluye(self, client, db):
        c, _, _, cita = _crear_cliente(db)
        from models import Servicio
        s = Servicio(nombre="Cambio de aceite")
        db.session.add(s)
        db.session.flush()
        cita.servicio_id = s.id
        db.session.commit()

        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        _logout(client)

        _crear_admin(db)
        _login(client, correo="admin_ubicacion@test.com")
        clientes = client.get("/api/admin/clientes-en-camino").get_json()["clientes"]
        assert clientes[0]["servicio_nombre"] == "Cambio de aceite"


class TestLimpiezaAlFinalizarCita:

    def test_entregar_cita_apaga_compartido(self, client, db):
        c, _, _, cita = _crear_cliente(db, estado="lista")
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        _logout(client)

        admin = _crear_admin(db)
        _login(client, correo="admin_ubicacion@test.com")
        r = client.post(f"/citas/cambiar-estado/{cita.id}/entregada",
                        follow_redirects=True)
        assert r.status_code == 200
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id).first()
        assert reg is not None
        assert reg.sharing_active is False
        _logout(client)

    def test_cancelar_via_portal_apaga_compartido(self, client, db):
        c, _, _, cita = _crear_cliente(db, estado="pendiente")
        _login(client)
        client.post("/api/ubicacion/actualizar", json=COORDS)
        r = client.post(f"/portal/citas/{cita.id}/cancelar", follow_redirects=True)
        assert r.status_code == 200
        reg = UbicacionCliente.query.filter_by(cliente_id=c.id).first()
        assert reg is not None
        assert reg.sharing_active is False