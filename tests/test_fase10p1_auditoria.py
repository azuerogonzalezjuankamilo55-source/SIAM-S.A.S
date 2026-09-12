"""FASE 10.1 - Auditoría funcional: pruebas de las correcciones realizadas.

Cubre: bootstrap de registrar-admin, formularios POST de citas (cambio de
estado), restricción admin de /configuracion/sistema/comprobar, numeración
secuencial y parseo de stock_bajo en inventario.
"""
from datetime import date, time

from models import (
    Usuario, Cliente, Vehiculo, Cita, Cotizacion, Servicio, Inventario,
)


def _crear_admin(db, correo="admin_f101@test.com"):
    u = Usuario(nombre="Admin", correo=correo, rol="admin")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _crear_mecanico(db, correo="mec_f101@test.com"):
    u = Usuario(nombre="Mecanico", correo=correo, rol="mecanico")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo="admin_f101@test.com", clave="clave1234"):
    return client.post("/auth/login", data={"correo": correo, "password": clave},
                       follow_redirects=True)


def _crear_cita(db, estado="pendiente"):
    c = Cliente(nombre="Cliente F101", correo="cf101@test.com", telefono="3001112233")
    db.session.add(c)
    db.session.flush()
    u = Usuario(nombre="Cliente F101", correo="cf101@test.com", rol="cliente",
                cliente_id=c.id)
    u.set_password("clave1234")
    db.session.add(u)
    v = Vehiculo(cliente_id=c.id, marca="Toyota", modelo="Corolla", placa="F101-01")
    db.session.add(v)
    db.session.flush()
    cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=date.today(),
                hora=time(10, 0), estado=estado)
    db.session.add(cita)
    db.session.commit()
    return c, v, cita


class TestRegistrarAdminBootstrap:

    def test_bloqueado_si_ya_existe_admin(self, client, db):
        _crear_admin(db)
        r = client.get("/auth/registrar-admin", follow_redirects=True)
        assert b"Ya existe una cuenta de administrador" in r.data

    def test_post_bloqueado_si_ya_existe_admin(self, client, db):
        _crear_admin(db)
        r = client.post("/auth/registrar-admin", data={
            "nombre": "Otro", "correo": "otro@test.com",
            "password": "clave1234", "confirmar": "clave1234",
        }, follow_redirects=True)
        assert b"Ya existe una cuenta de administrador" in r.data
        assert Usuario.query.filter_by(correo="otro@test.com").count() == 0

    def test_disponible_sin_admin_bootstrap(self, client, db):
        r = client.get("/auth/registrar-admin")
        assert r.status_code == 200
        r = client.post("/auth/registrar-admin", data={
            "nombre": "Primer Admin", "correo": "primer@test.com",
            "password": "clave1234", "confirmar_password": "clave1234",
        }, follow_redirects=True)
        assert r.status_code == 200
        u = Usuario.query.filter_by(correo="primer@test.com").first()
        assert u is not None
        assert u.rol == "admin"


class TestCitasCambioEstadoForm:

    def test_listado_usa_formulario_post(self, client, db):
        _crear_admin(db)
        _crear_cita(db)
        _login(client)
        html = client.get("/citas/").get_data(as_text=True)
        assert "/citas/cambiar-estado/1/confirmada" in html
        assert '<form method="post"' in html
        # El estado NO debe poder cambiarse con un GET (enlace roto eliminado).
        assert '<a href="/citas/cambiar-estado/' not in html

    def test_post_cambia_estado(self, client, db):
        _crear_admin(db)
        _, _, cita = _crear_cita(db)
        _login(client)
        r = client.post(f"/citas/cambiar-estado/{cita.id}/confirmada",
                        follow_redirects=True)
        assert r.status_code == 200
        estado = db.session.get(Cita, cita.id).estado
        assert estado == "confirmada"


class TestSistemaComprobarSoloAdmin:

    def test_mecanico_rechazado(self, client, db):
        _crear_admin(db)
        _crear_mecanico(db)
        _login(client, correo="mec_f101@test.com")
        r = client.post("/configuracion/sistema/comprobar",
                        headers={"Accept": "application/json"})
        assert r.status_code == 403
        assert r.get_json()["success"] is False

    def test_admin_ok(self, client, db):
        _crear_admin(db)
        _login(client)
        r = client.post("/configuracion/sistema/comprobar",
                        headers={"Accept": "application/json"})
        assert r.status_code == 200
        assert r.get_json()["success"] is True


class TestNumeracion:

    def test_secuencia_continua(self, client, db):
        from services.numeracion import siguiente_numero
        cl = Cliente(nombre="Cliente Num", correo="num@test.com")
        db.session.add(cl)
        db.session.flush()
        v = Vehiculo(cliente_id=cl.id, marca="Kia", modelo="Picanto", placa="NUM-01")
        db.session.add(v)
        db.session.flush()
        n1 = siguiente_numero(Cotizacion, "COT")
        c = Cotizacion(numero=n1, cliente_id=cl.id, vehiculo_id=v.id)
        db.session.add(c)
        db.session.commit()
        n2 = siguiente_numero(Cotizacion, "COT")
        assert n1 == "COT-000001"
        assert n2 == "COT-000002"

    def test_primera_tabla_vacia(self, client, db):
        from services.numeracion import siguiente_numero
        assert siguiente_numero(Cotizacion, "COT") == "COT-000001"
        assert siguiente_numero(Cotizacion, "COT", ancho=3) == "COT-001"


class TestInventarioStockBajo:

    def test_false_no_filtra(self, client, db):
        _crear_admin(db)
        bajo = Inventario(nombre="Aceite", cantidad=2, stock_minimo=5, activo=True)
        ok = Inventario(nombre="Grasa", cantidad=20, stock_minimo=5, activo=True)
        db.session.add_all([bajo, ok])
        db.session.commit()
        _login(client)

        html = client.get("/inventario/?stock_bajo=false").get_data(as_text=True)
        assert "Aceite" in html
        assert "Grasa" in html

        html = client.get("/inventario/?stock_bajo=1").get_data(as_text=True)
        assert "Aceite" in html
        assert "Grasa" not in html