"""FASE FINAL - Solicitud de asesor, aviso de ubicacion y comunicacion admin -> cliente.

Cubre los flujos completos exigidos en la integracion final:

* Solicitar asesor: creacion, pertenencia del vehiculo, estados y respuesta.
* Ubicacion: un aviso al iniciar el compartido y ninguno por GPS posterior.
* Comunicacion: ADMIN y RECEPCION pueden; CLIENTE y MECANICO no.
* Notificaciones: aviso al staff, lectura y contador de la campana.
* Aislamiento entre clientes y permisos reales de backend (no solo UI).

Las pruebas corren contra SQLite en memoria (`create_app("testing")`): no tocan
ninguna base de datos real ni ejecutan migraciones.
"""
from datetime import date, time, timedelta

from models import (
    Cliente,
    Usuario,
    Vehiculo,
    Cita,
    SolicitudAsesor,
    Notificacion,
    UbicacionCliente,
)

PASS = "clave1234"
COORDS = {"latitude": 4.710989, "longitude": -74.072090, "accuracy": 12.0}


# --------------------------------------------------------------------- helpers


def _usuario(db, correo, rol, nombre="Usuario", cliente_id=None):
    u = Usuario(nombre=nombre, correo=correo, rol=rol, cliente_id=cliente_id)
    u.set_password(PASS)
    db.session.add(u)
    db.session.flush()
    return u


def _staff(db):
    """Administrador, recepcion y mecanico: los tres roles del area administrativa."""
    _usuario(db, "admin_asesor@test.com", "admin", "Admin SIAM")
    _usuario(db, "recepcion_asesor@test.com", "recepcion", "Recepcion SIAM")
    _usuario(db, "mecanico_asesor@test.com", "mecanico", "Mecanico SIAM")
    db.session.commit()


def _cliente_con_vehiculo(db, nombre, correo, placa, estado_cita="confirmada", dias=0):
    """Cliente con cuenta, vehiculo propio y cita activa (para compartir ubicacion)."""
    c = Cliente(nombre=nombre, correo=correo, telefono="3001234567")
    db.session.add(c)
    db.session.flush()
    _usuario(db, correo, "cliente", nombre, c.id)
    v = Vehiculo(cliente_id=c.id, placa=placa, marca="Toyota", modelo="Corolla")
    db.session.add(v)
    db.session.flush()
    dia = date.today() + timedelta(days=dias)
    cita = Cita(cliente_id=c.id, vehiculo_id=v.id, fecha=dia,
                hora=time(10, 0), estado=estado_cita)
    db.session.add(cita)
    db.session.commit()
    return c, v, cita


def _login(client, correo, clave=PASS):
    """Cambiar de usuario exige salir primero: la sesion es compartida."""
    client.get("/auth/logout", follow_redirects=True)
    return client.post("/auth/login", data={"correo": correo, "password": clave},
                       follow_redirects=True)


def _n_notifs(tipo=None):
    q = Notificacion.query
    if tipo:
        q = q.filter_by(tipo=tipo)
    return q.count()


def _crear_solicitud(client, vehiculo_id=None, tipo="asesoria", **extra):
    data = {"tipo": tipo, "mensaje": "Necesito ayuda.", "asunto": "Consulta"}
    if vehiculo_id is not None:
        data["vehiculo_id"] = str(vehiculo_id)
    data.update(extra)
    return client.post("/portal/asesor", data=data, follow_redirects=True)


# ------------------------------------------------------- solicitud de asesor


class TestSolicitudAsesorCliente:

    def test_crea_solicitud_con_vehiculo_propio(self, client, db):
        c, v, _ = _cliente_con_vehiculo(db, "Ana Torres", "ana_asesor@test.com", "AAA111")
        _login(client, "ana_asesor@test.com")

        r = client.get("/portal/asesor")
        assert r.status_code == 200
        assert b'name="mensaje"' in r.data

        _crear_solicitud(client, vehiculo_id=v.id)
        s = SolicitudAsesor.query.one()
        assert s.cliente_id == c.id
        assert s.vehiculo_id == v.id
        assert s.estado == "pendiente"
        assert s.tipo == "asesoria"
        assert s.cliente_nombre == "Ana Torres"
        assert s.solicitante == "Ana Torres"

    def test_solicitud_sin_vehiculo_es_valida(self, client, db):
        _cliente_con_vehiculo(db, "Sin Moto", "sin_vehiculo@test.com", "BBB222")
        _login(client, "sin_vehiculo@test.com")

        _crear_solicitud(client, vehiculo_id=None)

        assert SolicitudAsesor.query.one().vehiculo_id is None

    def test_rechaza_vehiculo_de_otro_cliente(self, client, db):
        _cliente_con_vehiculo(db, "Dueño", "dueno@test.com", "CCC333")
        _cliente_con_vehiculo(db, "Ajeno", "ajeno@test.com", "DDD444")  # noqa: F841
        _login(client, "dueno@test.com")
        v_ajeno = Vehiculo.query.filter_by(placa="DDD444").one()

        r = _crear_solicitud(client, vehiculo_id=v_ajeno.id)

        assert SolicitudAsesor.query.count() == 0, "no debe crear la solicitud"
        assert "no pertenece a tu cuenta" in r.get_data(as_text=True)

    def test_rechaza_tipo_invalido(self, client, db):
        _cliente_con_vehiculo(db, "Tipos", "tipos@test.com", "EEE555")
        _login(client, "tipos@test.com")

        _crear_solicitud(client, tipo="sql_injection")

        assert SolicitudAsesor.query.count() == 0

    def test_cliente_solo_ve_sus_solicitudes(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_lista@test.com", "FFF666")
        _cliente_con_vehiculo(db, "Luis", "luis_lista@test.com", "GGG777")
        _login(client, "ana_lista@test.com")
        _crear_solicitud(client, asunto="Consulta de Ana")

        _login(client, "luis_lista@test.com")
        cuerpo = client.get("/portal/asesor").get_data(as_text=True)

        assert "Consulta de Ana" not in cuerpo
        assert "todav" in cuerpo.lower()

    def test_requiere_login(self, client):
        r = client.get("/portal/asesor", follow_redirects=False)

        assert r.status_code in (301, 302)
        assert "/auth/login" in r.headers.get("Location", "")

    def test_staff_no_entra_al_portal_de_asesor(self, client, db):
        _staff(db)
        _login(client, "admin_asesor@test.com")

        r = client.get("/portal/asesor", follow_redirects=False)

        assert r.status_code == 302
        assert "/dashboard/" in r.headers.get("Location", "")


class TestNotificacionDeSolicitud:

    def test_avisa_a_admin_y_recepcion(self, client, db):
        _cliente_con_vehiculo(db, "Notificada", "notificada@test.com", "HHH888")
        _staff(db)
        _login(client, "notificada@test.com")

        _crear_solicitud(client)

        assert _n_notifs("asesor") == 2, "admin + recepcion reciben el aviso"
        aviso = Notificacion.query.filter_by(tipo="asesor").first()
        assert "/sedes/asesores" in aviso.url

    def test_staff_ve_el_aviso_en_su_campana(self, client, db):
        _cliente_con_vehiculo(db, "Campana", "campana@test.com", "III999")
        _staff(db)
        _login(client, "campana@test.com")
        _crear_solicitud(client)

        _login(client, "admin_asesor@test.com")
        cuerpo = client.get("/notificaciones/api/listar").get_data(as_text=True)

        assert "asesor" in cuerpo.lower()


class TestPanelDeAsesores:

    def test_admin_ve_filtra_y_responde(self, client, db):
        c, v, _ = _cliente_con_vehiculo(db, "Ana", "ana_panel@test.com", "JJJ100")
        _staff(db)
        _login(client, "ana_panel@test.com")
        _crear_solicitud(client, vehiculo_id=v.id, asunto="Revisar garantia")
        s = SolicitudAsesor.query.one()

        _login(client, "admin_asesor@test.com")
        r = client.get("/sedes/asesores")
        assert r.status_code == 200
        assert "Revisar garantia" in r.get_data(as_text=True)

        # Pendiente -> En atencion, con respuesta al cliente.
        r = client.post(f"/sedes/asesores/{s.id}/estado",
                        data={"estado": "en_atencion", "respuesta": "Ya lo miramos.",
                              "estado_filtro": "pendiente"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/sedes/asesores?estado=pendiente")
        assert s.estado == "en_atencion"
        assert s.respuesta == "Ya lo miramos."
        assert _n_notifs("asesor") == 3, "2 avisos al staff + 1 al cliente"

        # El cliente ve la respuesta del taller.
        _login(client, "ana_panel@test.com")
        cuerpo = client.get("/portal/asesor").get_data(as_text=True)
        assert "Ya lo miramos." in cuerpo
        assert "En atenci" in cuerpo

        # En atencion -> Atendida.
        _login(client, "recepcion_asesor@test.com")
        client.post(f"/sedes/asesores/{s.id}/estado",
                    data={"estado": "atendida", "respuesta": "Listo.",
                          "estado_filtro": "en_atencion"}, follow_redirects=False)
        assert s.estado == "atendida"
        assert s.esta_abierta is False

    def test_recepcion_tiene_el_mismo_acceso(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_recep@test.com", "A0A100")
        _staff(db)
        _login(client, "ana_recep@test.com")
        _crear_solicitud(client)
        s = SolicitudAsesor.query.one()

        _login(client, "recepcion_asesor@test.com")
        assert client.get("/sedes/asesores").status_code == 200
        client.post(f"/sedes/asesores/{s.id}/estado",
                    data={"estado": "en_atencion", "respuesta": "Recepcion responde."},
                    follow_redirects=False)

        assert s.estado == "en_atencion"

    def test_filtro_por_estado(self, client, db):
        _cliente_con_vehiculo(db, "Filtro", "filtro_panel@test.com", "A1A200")
        _staff(db)
        _login(client, "filtro_panel@test.com")
        _crear_solicitud(client, asunto="Pendiente de verdad")

        _login(client, "admin_asesor@test.com")
        assert "Pendiente de verdad" in client.get(
            "/sedes/asesores?estado=pendiente").get_data(as_text=True)
        assert "Pendiente de verdad" not in client.get(
            "/sedes/asesores?estado=atendida").get_data(as_text=True)

    def test_pendiente_a_cancelada(self, client, db):
        _cliente_con_vehiculo(db, "Cancela", "cancela_panel@test.com", "A2A300")
        _staff(db)
        _login(client, "cancela_panel@test.com")
        _crear_solicitud(client)
        s = SolicitudAsesor.query.one()

        _login(client, "admin_asesor@test.com")
        client.post(f"/sedes/asesores/{s.id}/estado",
                    data={"estado": "cancelada", "respuesta": "No aplica."},
                    follow_redirects=False)

        assert s.estado == "cancelada"

        _login(client, "cancela_panel@test.com")
        cuerpo = client.get("/portal/asesor").get_data(as_text=True)
        assert "Cancelada" in cuerpo
        assert "No aplica." in cuerpo

    def test_no_modifica_solicitud_finalizada(self, client, db):
        _cliente_con_vehiculo(db, "Final", "final_panel@test.com", "A3A400")
        _staff(db)
        _login(client, "final_panel@test.com")
        _crear_solicitud(client)
        s = SolicitudAsesor.query.one()

        _login(client, "admin_asesor@test.com")
        client.post(f"/sedes/asesores/{s.id}/estado",
                    data={"estado": "atendida"}, follow_redirects=False)
        client.post(f"/sedes/asesores/{s.id}/estado",
                    data={"estado": "en_atencion"}, follow_redirects=True)

        assert s.estado == "atendida", "una solicitud cerrada no se reabre"

    def test_rechaza_estado_inventado(self, client, db):
        _cliente_con_vehiculo(db, "Inventado", "inventado_panel@test.com", "A4A500")
        _staff(db)
        _login(client, "inventado_panel@test.com")
        _crear_solicitud(client)
        s = SolicitudAsesor.query.one()

        _login(client, "admin_asesor@test.com")
        client.post(f"/sedes/asesores/{s.id}/estado",
                    data={"estado": "hackeado"}, follow_redirects=False)

        assert s.estado == "pendiente"

    def test_mecanico_no_tiene_panel(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_mec@test.com", "A5A600")
        _staff(db)
        _login(client, "mecanico_asesor@test.com")

        r = client.get("/sedes/asesores", follow_redirects=False)

        assert r.status_code == 302
        assert "/dashboard/" in r.headers.get("Location", "")

    def test_mecanico_no_cambia_estados(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_mec2@test.com", "A6A700")
        _staff(db)
        _login(client, "ana_mec2@test.com")
        _crear_solicitud(client)
        s = SolicitudAsesor.query.one()

        _login(client, "mecanico_asesor@test.com")
        r = client.post(f"/sedes/asesores/{s.id}/estado",
                        data={"estado": "atendida", "respuesta": "No autorizado."},
                        follow_redirects=False)

        assert r.status_code in (301, 302)
        assert s.estado == "pendiente"
        assert s.respuesta is None

    def test_cliente_no_abre_el_panel(self, client, db):
        _cliente_con_vehiculo(db, "Curioso", "curioso_panel@test.com", "A7A800")
        _staff(db)
        _login(client, "curioso_panel@test.com")

        r = client.get("/sedes/asesores", follow_redirects=False)

        assert r.status_code == 302
        assert "/portal/" in r.headers.get("Location", "")

    def test_panel_requiere_login(self, client):
        r = client.get("/sedes/asesores", follow_redirects=False)

        assert r.status_code in (301, 302)
        assert "/auth/login" in r.headers.get("Location", "")


# ------------------------------------------------- aviso de iniciar ubicación


class TestAvisoDeUbicacion:

    def test_primera_actualizacion_avisa_al_staff(self, client, db):
        _cliente_con_vehiculo(db, "Geo", "geo_asesor@test.com", "B0B600")
        _staff(db)
        _login(client, "geo_asesor@test.com")

        r = client.post("/api/ubicacion/actualizar", json=COORDS)

        assert r.status_code == 200
        assert UbicacionCliente.query.one().sharing_active is True
        assert _n_notifs("asistencia") == 2, "admin + recepcion"

    def test_gps_posteriores_no_duplican_el_aviso(self, client, db):
        _cliente_con_vehiculo(db, "Geo2", "geo2_asesor@test.com", "B1B700")
        _staff(db)
        _login(client, "geo2_asesor@test.com")

        client.post("/api/ubicacion/actualizar", json=COORDS)
        primera = _n_notifs("asistencia")

        for i in range(6):
            r = client.post("/api/ubicacion/actualizar",
                            json={"latitude": 4.71 + i * 0.001,
                                  "longitude": -74.07, "accuracy": 9.0})
            assert r.status_code == 200

        assert _n_notifs("asistencia") == primera, "un aviso por sesion, no por GPS"
        assert UbicacionCliente.query.one().sharing_active is True

    def test_admin_consulta_los_clientes_en_camino(self, client, db):
        _cliente_con_vehiculo(db, "Mapa", "mapa_asesor@test.com", "B2B800")
        _staff(db)
        _login(client, "mapa_asesor@test.com")
        client.post("/api/ubicacion/actualizar", json=COORDS)

        _login(client, "admin_asesor@test.com")
        cuerpo = client.get("/api/admin/clientes-en-camino").get_data(as_text=True)

        assert "Mapa" in cuerpo

    def test_detiene_al_entregar_la_cita(self, client, db):
        c, _, cita = _cliente_con_vehiculo(db, "Entregada", "entregada_asesor@test.com", "B3B900")
        _staff(db)
        _login(client, "entregada_asesor@test.com")
        client.post("/api/ubicacion/actualizar", json=COORDS)
        assert UbicacionCliente.query.one().sharing_active is True

        _login(client, "admin_asesor@test.com")
        client.post(f"/citas/cambiar-estado/{cita.id}/entregada", follow_redirects=True)

        db.session.refresh(cita)
        assert cita.estado == "entregada"
        assert UbicacionCliente.query.one().sharing_active is False, \
            "una cita entregada debe apagar el seguimiento"

    def test_detiene_al_cancelar_la_cita_por_el_cliente(self, client, db):
        _cliente_con_vehiculo(db, "Cancela Geo", "cancelageo_asesor@test.com", "B4C100",
                              estado_cita="pendiente", dias=5)
        _staff(db)
        _login(client, "cancelageo_asesor@test.com")
        client.post("/api/ubicacion/actualizar", json=COORDS)
        cita = Cita.query.filter_by(estado="pendiente").one()

        client.post(f"/portal/citas/{cita.id}/cancelar", follow_redirects=True)

        db.session.refresh(cita)
        assert cita.estado == "cancelado"
        assert UbicacionCliente.query.one().sharing_active is False, \
            "cancelar la cita debe apagar el seguimiento"

    def test_cliente_puede_apagar_su_ubicacion(self, client, db):
        _cliente_con_vehiculo(db, "Apaga", "apaga_asesor@test.com", "B5C200")
        _login(client, "apaga_asesor@test.com")
        client.post("/api/ubicacion/actualizar", json=COORDS)

        r = client.post("/api/ubicacion/detener", json={}, follow_redirects=False)

        assert r.status_code == 200
        assert UbicacionCliente.query.one().sharing_active is False

    def test_un_nuevo_compartido_vuelve_a_avisar(self, client, db):
        _cliente_con_vehiculo(db, "Reabre", "reabre_asesor@test.com", "B6C300")
        _staff(db)
        _login(client, "reabre_asesor@test.com")
        client.post("/api/ubicacion/actualizar", json=COORDS)
        client.post("/api/ubicacion/detener", json={})
        primera = _n_notifs("asistencia")

        client.post("/api/ubicacion/actualizar", json=COORDS)

        assert _n_notifs("asistencia") == primera + 2, "un nuevo compartido si avisa"


# ----------------------------------------------- comunicación admin -> cliente


class TestComunicacionAdminCliente:

    def test_admin_puede_notificar(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Notificado", "notif_admin@test.com", "B7C400")
        _staff(db)
        _login(client, "admin_asesor@test.com")

        r = client.post(f"/clientes/{c.id}/notificar",
                        data={"titulo": "Tu carro esta listo",
                              "mensaje": "Puedes pasar a recogerlo."},
                        follow_redirects=True)

        assert r.status_code == 200
        assert _n_notifs("orden") == 1

        _login(client, "notif_admin@test.com")
        cuerpo = client.get("/notificaciones/api/listar").get_data(as_text=True)
        assert "Tu carro esta listo" in cuerpo

    def test_recepcion_puede_notificar(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Notificado 2", "notif_recep@test.com", "B8C500")
        _staff(db)
        _login(client, "recepcion_asesor@test.com")

        r = client.post(f"/clientes/{c.id}/notificar",
                        data={"titulo": "Tu servicio avanzo",
                              "mensaje": "Estamos con el cambio de aceite."},
                        follow_redirects=True)

        assert r.status_code == 200
        assert _n_notifs("orden") == 1

    def test_cliente_no_puede_usar_el_endpoint(self, client, db):
        c_ajeno, _, _ = _cliente_con_vehiculo(db, "Victima", "victima@test.com", "B9C600")
        _cliente_con_vehiculo(db, "Atacante", "atacante@test.com", "C0C700")
        _staff(db)
        _login(client, "atacante@test.com")

        r = client.post(f"/clientes/{c_ajeno.id}/notificar",
                        data={"titulo": "Hack", "mensaje": "Mensaje inyectado."},
                        follow_redirects=False)

        assert r.status_code in (301, 302), "un cliente no envia comunicaciones"
        assert _n_notifs() == 0

    def test_mecanico_no_puede_usar_el_endpoint(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Orden", "orden_mec@test.com", "C1C800")
        _staff(db)
        _login(client, "mecanico_asesor@test.com")

        r = client.post(f"/clientes/{c.id}/notificar",
                        data={"titulo": "No autorizado", "mensaje": "..."},
                        follow_redirects=False)

        assert r.status_code in (301, 302)
        assert _n_notifs() == 0

    def test_exige_mensaje(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Vacio", "vacio_notif@test.com", "C2C900")
        _staff(db)
        _login(client, "admin_asesor@test.com")

        r = client.post(f"/clientes/{c.id}/notificar",
                        data={"titulo": "Sin cuerpo", "mensaje": ""},
                        follow_redirects=True)

        assert "Escribe el mensaje" in r.get_data(as_text=True)
        assert _n_notifs() == 0

    def test_avisa_si_el_cliente_no_tiene_cuenta(self, client, db):
        c = Cliente(nombre="Sin Cuenta", correo="sin_cuenta@test.com")
        db.session.add(c)
        db.session.commit()
        _staff(db)
        _login(client, "admin_asesor@test.com")

        r = client.post(f"/clientes/{c.id}/notificar",
                        data={"titulo": "Hola", "mensaje": "Mensaje"}, follow_redirects=True)

        assert "no tiene una cuenta" in r.get_data(as_text=True)
        assert _n_notifs() == 0

    def test_modal_presente_en_la_lista(self, client, db):
        _cliente_con_vehiculo(db, "Listado", "listado_notif@test.com", "C3D100")
        _staff(db)
        _login(client, "admin_asesor@test.com")

        cuerpo = client.get("/clientes/").get_data(as_text=True)

        assert "modalNotificar" in cuerpo
        assert "Avisos rápidos" in cuerpo


# ------------------------------------------------------------ notificaciones


class TestNotificaciones:

    def test_leer_una_notificacion(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Lector", "lector_notif@test.com", "C4D200")
        _staff(db)
        _login(client, "admin_asesor@test.com")
        client.post(f"/clientes/{c.id}/notificar",
                    data={"titulo": "Aviso", "mensaje": "Contenido"}, follow_redirects=True)
        n = Notificacion.query.one()
        assert n.leida is False

        _login(client, "lector_notif@test.com")
        r = client.post(f"/notificaciones/api/leer/{n.id}", json={})

        assert r.status_code == 200
        assert Notificacion.query.one().leida is True

    def test_leer_todas(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Todas", "todas_notif@test.com", "C5D300")
        _staff(db)
        _login(client, "admin_asesor@test.com")
        for i in range(3):
            client.post(f"/clientes/{c.id}/notificar",
                        data={"titulo": f"Aviso {i}", "mensaje": "x"},
                        follow_redirects=True)

        _login(client, "todas_notif@test.com")
        client.post("/notificaciones/api/leer-todas", json={})

        assert Notificacion.query.filter_by(leida=False).count() == 0

    def test_contador_de_la_campana(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Contador", "contador_notif@test.com", "C6D400")
        _staff(db)
        _login(client, "admin_asesor@test.com")
        client.post(f"/clientes/{c.id}/notificar",
                    data={"titulo": "Uno", "mensaje": "x"}, follow_redirects=True)

        _login(client, "contador_notif@test.com")
        cuerpo = client.get("/notificaciones/api/listar").get_data(as_text=True)

        assert '"no_leidas":1' in cuerpo.replace(" ", "")

    def test_no_lee_avisos_de_otro_usuario(self, client, db):
        _cliente_con_vehiculo(db, "Dueña", "duena_notif@test.com", "C7D500")
        _cliente_con_vehiculo(db, "Curiosa", "curiosa_notif@test.com", "C8D600")
        _staff(db)
        _login(client, "duena_notif@test.com")
        _crear_solicitud(client, asunto="Aviso privado")
        avisos = Notificacion.query.filter_by(tipo="asesor").all()
        assert len(avisos) == 2, "los avisos son para admin y recepcion"
        propia = Usuario.query.filter_by(correo="curiosa_notif@test.com").one()

        _login(client, "curiosa_notif@test.com")
        cuerpo = client.get("/notificaciones/api/listar").get_data(as_text=True)
        for aviso in avisos:
            assert aviso.usuario_id != propia.id, "el aviso es de otro usuario"
            r = client.post(f"/notificaciones/api/leer/{aviso.id}", json={})
            assert r.status_code != 200, "no marca como leido un aviso ajeno"

        assert "Aviso privado" not in cuerpo
        assert Notificacion.query.filter_by(leida=True).count() == 0


# -------------------------------------------------------------- aislamiento


class TestAislamientoDeClientes:

    def test_no_ve_vehiculos_de_otro(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_iso@test.com", "D0E100")
        _cliente_con_vehiculo(db, "Luis", "luis_iso@test.com", "D1E200")
        _login(client, "ana_iso@test.com")

        cuerpo = client.get("/portal/vehiculos").get_data(as_text=True)

        assert "D0E100" in cuerpo, "ve su propio vehiculo"
        assert "D1E200" not in cuerpo, "no ve el vehiculo ajeno"

    def test_no_ve_citas_de_otro(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_iso2@test.com", "D2E300")
        _cliente_con_vehiculo(db, "Luis", "luis_iso2@test.com", "D3E400")
        _login(client, "luis_iso2@test.com")
        cita_luis = Cita.query.filter_by(estado="confirmada").all()[-1]

        r = client.get(f"/portal/citas/{cita_luis.id}/editar", follow_redirects=False)

        assert r.status_code in (301, 302, 404), "no puede editar la cita ajena"

    def test_no_abre_comunicaciones_de_otro(self, client, db):
        _cliente_con_vehiculo(db, "Ana", "ana_iso3@test.com", "D4E500")
        _cliente_con_vehiculo(db, "Luis", "luis_iso3@test.com", "D5E600")
        _staff(db)
        _login(client, "admin_asesor@test.com")
        c_luis = Cliente.query.filter_by(correo="luis_iso3@test.com").one()
        client.post(f"/clientes/{c_luis.id}/notificar",
                    data={"titulo": "Privado de Luis", "mensaje": "Secreto"},
                    follow_redirects=True)

        _login(client, "ana_iso3@test.com")
        cuerpo = client.get("/notificaciones/api/listar").get_data(as_text=True)

        assert "Privado de Luis" not in cuerpo
        assert "Secreto" not in cuerpo

    def test_no_modifica_datos_de_otro_cliente(self, client, db):
        c_ana, _, _ = _cliente_con_vehiculo(db, "Ana", "ana_iso4@test.com", "D6E700")
        c_luis, _, _ = _cliente_con_vehiculo(db, "Luis", "luis_iso4@test.com", "D7E800")
        _staff(db)
        _login(client, "ana_iso4@test.com")

        # Ni propio ni ajeno: la ficha de cliente es solo del area administrativa.
        for objetivo in (c_ana, c_luis):
            r = client.post(f"/clientes/editar/{objetivo.id}",
                            data={"nombre": "Ana Robada"}, follow_redirects=False)
            assert r.status_code in (301, 302), "el cliente no edita fichas"

        assert db.session.get(Cliente, c_ana.id).nombre == "Ana"
        assert db.session.get(Cliente, c_luis.id).nombre == "Luis"

    def test_admin_si_puede_editar_ficha(self, client, db):
        c, _, _ = _cliente_con_vehiculo(db, "Ana", "ana_iso5@test.com", "D9F000")
        _staff(db)
        _login(client, "admin_asesor@test.com")

        r = client.post(f"/clientes/editar/{c.id}",
                        data={"nombre": "Ana Editada", "correo": c.correo},
                        follow_redirects=False)

        assert r.status_code == 302
        assert db.session.get(Cliente, c.id).nombre == "Ana Editada"


# --------------------------------------------------------------- boton chat


class TestBotonDeAsesorEnElChat:

    def test_cliente_recibe_la_url_del_formulario(self, client, db):
        _cliente_con_vehiculo(db, "Chat", "chat_asesor@test.com", "D8E900")
        _login(client, "chat_asesor@test.com")

        cuerpo = client.get("/asistente/").get_data(as_text=True)

        assert 'data-url-asesor="/portal/asesor"' in cuerpo

    def test_staff_no_recibe_la_url_del_formulario(self, client, db):
        _staff(db)
        _login(client, "admin_asesor@test.com")

        cuerpo = client.get("/asistente/").get_data(as_text=True)

        assert 'data-url-asesor=""' in cuerpo

    def test_el_js_ya_no_tiene_el_toast_falso(self, app):
        import pathlib

        js = pathlib.Path(app.root_path, "static", "js", "siam.js").read_text(encoding="utf-8")

        assert "Conectando con un asesor" not in js
        assert "data-url-asesor" in js
