"""FASE 26 - Destino por rol, campana de notificaciones y toma de cuentas.

Cubre las regresiones corregidas en esta fase:
- un cliente SIEMPRE cae en su portal, nunca en el area administrativa,
- un rol desconocido tampoco cae en el dashboard (fail-safe),
- la busqueda del navbar (destinos administrativos) no se renderiza a clientes,
- el menu de notificaciones esta oculto por defecto: declararle `display` en el
  selector base anulaba el `display: none` de Bootstrap y lo dejaba siempre
  visible, con el boton alternando `.show` sin efecto visual,
- el registro publico no puede vincularse a un Cliente que ya esta en uso.
"""
import re
from pathlib import Path

import pytest

from models import Usuario, Cliente, Vehiculo, Notificacion
from services.assistant_service import AssistantService


RAIZ = Path(__file__).resolve().parent.parent
CSS_NAVBAR = RAIZ / "static" / "css" / "navbar.css"
CSS_SIAM = RAIZ / "static" / "css" / "siam.css"

RUTAS_ADMINISTRATIVAS = [
    "/dashboard/",
    "/clientes/",
    "/vehiculos/",
    "/facturas/",
    "/inventario/",
    "/ordenes-trabajo/",
    "/configuracion/",
]


# ---------------------------------------------------------------- helpers


def _usuario(db, correo, rol, nombre="Usuario", cliente_id=None):
    u = Usuario(nombre=nombre, correo=correo, rol=rol, cliente_id=cliente_id)
    u.set_password("clave1234")
    db.session.add(u)
    db.session.flush()
    return u


def _cliente_con_usuario(db, nombre, slug):
    cli = Cliente(nombre=nombre, telefono="3001234567")
    db.session.add(cli)
    db.session.flush()
    u = _usuario(db, f"{slug}@test.com", "cliente", nombre=nombre, cliente_id=cli.id)
    db.session.commit()
    return cli, u


def _login(client, correo, password="clave1234", **kwargs):
    return client.post(
        "/auth/login",
        data={"correo": correo, "password": password},
        follow_redirects=True,
        **kwargs,
    )


def _registro(client, nombre, correo, documento, telefono="3001234567", clave="clave1234"):
    return client.post(
        "/auth/register",
        data={
            "nombre": nombre,
            "correo": correo,
            "password": clave,
            "confirmar_password": clave,
            "documento": documento,
            "telefono": telefono,
        },
        follow_redirects=True,
    )


def _regla(css: str, selector: str) -> str:
    """Devuelve el cuerpo de la primera regla `selector` de un texto CSS."""
    coincide = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert coincide, f"no se encontro la regla {selector}"
    return coincide.group(1)


# ------------------------------------------------- destino por rol en login


def test_login_cliente_termina_en_portal(app, client, db):
    """Un cliente autenticado nunca debe aparecer en el area administrativa."""
    _cliente_con_usuario(db, "Cliente Uno", "cliuno")
    respuesta = _login(client, "cliuno@test.com")

    assert respuesta.status_code == 200
    assert respuesta.request.path == "/portal/"
    # Contenido inequivocamente administrativo: no debe estar presente.
    assert b"/dashboard/api/resumen" not in respuesta.data


@pytest.mark.parametrize("rol", ["admin", "recepcion", "mecanico"])
def test_login_staff_termina_en_dashboard(app, client, db, rol):
    """Admin y personal del taller si deben entrar al area administrativa."""
    _usuario(db, f"{rol}@test.com", rol, nombre=f"Staff {rol}")
    respuesta = _login(client, f"{rol}@test.com")

    assert respuesta.status_code == 200
    assert respuesta.request.path == "/dashboard/"


def test_area_home_es_la_unica_fuente_de_destino(app, db):
    """Cliente -> portal; staff -> dashboard. Fuente unica en el modelo."""
    _cliente_con_usuario(db, "Cliente Dos", "clidos")
    cliente = Usuario.query.filter_by(correo="clidos@test.com").first()
    assert cliente.area_home == "portal.index"
    assert cliente.area == Usuario.AREA_PORTAL_CLIENTE

    for rol in ("admin", "recepcion", "mecanico"):
        u = _usuario(db, f"{rol}x@test.com", rol)
        assert u.area_home == "dashboard.index"
        assert u.area == Usuario.AREA_ADMINISTRATIVA


def test_registro_cliente_termina_en_portal(app, client, db):
    """El registro de un cliente nuevo lo deja en su portal, no en el dashboard."""
    respuesta = _registro(client, "Cliente Nuevo", "nuevo@test.com", "CC-1001")

    assert respuesta.status_code == 200
    assert respuesta.request.path == "/portal/"

    usuario = Usuario.query.filter_by(correo="nuevo@test.com").first()
    assert usuario is not None
    assert usuario.rol == "cliente"
    assert usuario.cliente_id is not None


def test_rol_desconocido_no_cae_en_el_dashboard(app, db):
    """Un rol no reconocido no habilita por error el area administrativa."""
    usuario = _usuario(db, "raro@test.com", "superusuario", nombre="Rol raro")
    db.session.commit()

    assert usuario.es_staff is False
    assert usuario.area_home == "portal.index"
    assert usuario.area == Usuario.AREA_PORTAL_CLIENTE


# ------------------------------------------- proteccion de rutas admin


@pytest.mark.parametrize("ruta", RUTAS_ADMINISTRATIVAS)
def test_cliente_es_expulsado_de_ruta_administrativa(app, client, db, ruta):
    """Un cliente que escriba una URL administrativa no entra: va a su portal."""
    _cliente_con_usuario(db, "Cliente Tres", "clitres")
    _login(client, "clitres@test.com")

    respuesta = client.get(ruta, follow_redirects=True)

    assert respuesta.request.path == "/portal/"
    assert b"Panel de control" not in respuesta.data


def test_cliente_no_ve_contenido_administrativo_al_pedirlo_directamente(app, client, db):
    """El HTML del dashboard no se entrega ni con follow_redirects."""
    _cliente_con_usuario(db, "Cliente Cuatro", "clicuatro")
    _login(client, "clicuatro@test.com")

    respuesta = client.get("/dashboard/")

    assert respuesta.status_code == 302
    assert "/portal/" in respuesta.headers["Location"]


# ------------------------------------------------------ navbar solo staff


def test_busqueda_del_navbar_no_se_renderiza_para_clientes(app, client, db):
    """La busqueda navega a URLs administrativas: no puede ofrecerse a un cliente."""
    _cliente_con_usuario(db, "Cliente Cinco", "cliquinco")
    _login(client, "cliquinco@test.com")

    html = client.get("/portal/").data.decode()
    assert 'id="navbarSearch"' not in html


def test_busqueda_del_navbar_si_se_renderiza_para_staff(app, client, db):
    _usuario(db, "staffnav@test.com", "recepcion", nombre="Recepcion")
    _login(client, "staffnav@test.com")

    html = client.get("/dashboard/").data.decode()
    assert 'id="navbarSearch"' in html
    # Los destinos que Salisbury navigation hardcodea son rutas administrativas.
    assert "data-staff-search" in html


# ------------------------------- campana de notificaciones: render y CSS


def test_campana_solo_para_usuarios_autenticados(app, client, db):
    """Anonimos no ven ni la campana ni el dropdown."""
    html = client.get("/", follow_redirects=True).data.decode()
    assert 'id="notifToggle"' not in html
    assert 'id="notificacionesDropdown"' not in html


def test_campana_se_renderiza_una_sola_vez_para_autenticados(app, client, db):
    """Debe existir una unica implementacion: un boton y un menu."""
    _usuario(db, "campana@test.com", "admin", nombre="Admin Campana")
    _login(client, "campana@test.com")

    html = client.get("/dashboard/").data.decode()
    assert html.count('id="notifToggle"') == 1
    assert html.count('id="notificacionesDropdown"') == 1
    # El menu se apoya en Bootstrap, no en un toggle propio en JS.
    assert 'data-bs-toggle="dropdown"' in html
    js = (RAIZ / "static" / "js" / "siam.js").read_text(encoding="utf-8")
    assert "new bootstrap.Dropdown" not in js


def test_menu_notificaciones_oculto_por_defecto():
    """Regresion del bug: `display` en `.notif-menu` anulaba el ocultado de Bootstrap.

    Bootstrap solo oculta con `.dropdown-menu{display:none}` y abre con
    `.dropdown-menu.show{display:block}`. Si el selector base declara `display`,
    gana por orden de fuente y el menu queda siempre visible.
    """
    navbar = CSS_NAVBAR.read_text(encoding="utf-8")

    base = _regla(navbar, ".notif-menu")
    assert "display" not in base, (
        ".notif-menu no debe declarar 'display': anula el display:none de Bootstrap"
    )

    abierto = _regla(navbar, ".notif-menu.show")
    assert re.search(r"display\s*:\s*flex", abierto), (
        "al abrirse debe recuperar el layout flex de columna"
    )


def test_siam_css_no_redefine_el_menu_de_notificaciones():
    """La hoja duplicaba `.notif-menu`; con dos fuentes gana la ultima en cargar."""
    siam = CSS_SIAM.read_text(encoding="utf-8")
    assert not re.search(r"\.notif-menu\s*\{[^}]*display", siam), (
        "siam.css no debe volver a declarar el menu de notificaciones"
    )


# ------------------------------------------- registro no toma cuentas ajenas


def test_registro_no_adopta_cliente_con_historial(app, client, db):
    """Conocer el correo de un cliente NO debe permitir quedarse con su cuenta.

    La victima es una ficha ya en uso (tiene vehiculo) pero todavia sin cuenta:
    es justo el caso que el auto-enlace por correo dejaba abierto.
    """
    victima = Cliente(nombre="Cliente Real", correo="clientereal@test.com",
                      telefono="3001111111")
    db.session.add(victima)
    db.session.flush()
    db.session.add(
        Vehiculo(cliente_id=victima.id, placa="XYZ789", marca="Toyota",
                 modelo="Hilux", anio=2021, tipo="camioneta")
    )
    db.session.commit()
    assert victima.usuario is None

    respuesta = _registro(client, "Atacante", "clientereal@test.com", "CC-9999")

    assert respuesta.request.path == "/auth/register"
    assert b"ficha de cliente" in respuesta.data
    # No se crea ninguna cuenta nueva ni se roba la ficha existente.
    assert Usuario.query.filter_by(correo="clientereal@test.com").first() is None
    assert victima.usuario is None
    assert victima.nombre == "Cliente Real"


def test_registro_no_adopta_cliente_por_documento(app, client, db):
    """Un documento sin correo no habilita a reclamar la cuenta de otro."""
    victima = Cliente(nombre="Victima Sin Correo", cedula="CC900", telefono="3009999999")
    db.session.add(victima)
    db.session.commit()

    respuesta = _registro(client, "Atacante", "atacante@evil.com", "CC900")

    assert respuesta.request.path == "/auth/register"
    assert b"documento ya est" in respuesta.data.lower()
    assert Usuario.query.filter_by(correo="atacante@evil.com").first() is None
    assert victima.usuario is None


def test_registro_sigue_vinculando_un_cliente_virgin(app, client, db):
    """El flujo legitimo "el taller me creo la ficha y la activo" se conserva."""
    precreado = Cliente(nombre="Cliente Virgin", correo="virgin@test.com", cedula="CC-777")
    db.session.add(precreado)
    db.session.commit()

    respuesta = _registro(client, "Cliente Virgin", "virgin@test.com", "CC-777")

    assert respuesta.request.path == "/portal/"
    usuario = Usuario.query.filter_by(correo="virgin@test.com").first()
    assert usuario is not None
    assert usuario.cliente_id == precreado.id


# ------------------------------------------------------- destino con next


def test_login_respeta_next_interno(app, client, db):
    _usuario(db, "nextok@test.com", "admin", nombre="Admin Next")
    respuesta = client.post(
        "/auth/login?next=/ordenes-trabajo/",
        data={"correo": "nextok@test.com", "password": "clave1234"},
        follow_redirects=True,
    )
    assert respuesta.request.path == "/ordenes-trabajo/"


@pytest.mark.parametrize("destino", ["https://evil.com/", "//evil.com/"])
def test_login_ignora_next_externo(app, client, db, destino):
    """`next` nunca debe usarse para sacar al usuario del sitio."""
    _cliente_con_usuario(db, "Cliente Next", "clinext")
    respuesta = client.post(
        f"/auth/login?next={destino}",
        data={"correo": "clinext@test.com", "password": "clave1234"},
        follow_redirects=True,
    )
    assert respuesta.request.path == "/portal/"


# ------------------------------------------------- aislamiento entre clientes


def test_cliente_no_ve_vehiculos_de_otro_cliente(app, client, db):
    """Cambiar el id en la URL no debe sacar un vehiculo ajeno."""
    _cli_a, _ = _cliente_con_usuario(db, "Cliente A", "clia")
    cli_b, _ = _cliente_con_usuario(db, "Cliente B", "clib")
    ajeno = Vehiculo(cliente_id=cli_b.id, placa="BBB111", marca="Kia",
                     modelo="Rio", anio=2020, tipo="carro")
    db.session.add(ajeno)
    db.session.commit()

    _login(client, "clia@test.com")
    respuesta = client.get(f"/portal/vehiculos/{ajeno.id}", follow_redirects=True)

    assert respuesta.request.path == "/portal/vehiculos"
    assert b"BBB111" not in respuesta.data


def test_cliente_no_toca_las_notificaciones_de_otro_usuario(app, client, db):
    """Marcar o borrar la notificacion de otro debe rechazarse sin alterarla."""
    _cli_a, usuario_a = _cliente_con_usuario(db, "Cliente Notif A", "clinota")
    _cli_b, _ = _cliente_con_usuario(db, "Cliente Notif B", "clinotb")
    ajena = Notificacion(
        usuario_id=usuario_a.id, tipo="sistema", titulo="Aviso privado",
        mensaje="Solo para A", leida=False,
    )
    db.session.add(ajena)
    db.session.commit()

    _login(client, "clinotb@test.com")

    # La API responde 404: el servicio filtra por usuario_id, no por el id de la URL.
    assert client.post(f"/notificaciones/api/leer/{ajena.id}").status_code == 404
    assert client.post(
        f"/notificaciones/api/leer/{ajena.id}",
        headers={"Accept": "application/json"},
    ).status_code == 404

    # El formulario HTML rebota sin borrar nada: lo que importa es el estado.
    respuesta = client.post(f"/notificaciones/eliminar/{ajena.id}", follow_redirects=True)
    assert respuesta.request.path == "/notificaciones/"
    assert b"Notificaci\xf3n eliminada" not in respuesta.data

    db.session.refresh(ajena)
    assert ajena.leida is False


def test_contador_de_no_leidas_es_solo_del_usuario_actual(app, client, db):
    """El badge no puede contar avisos de otra cuenta."""
    _cli_a, usuario_a = _cliente_con_usuario(db, "Cliente Cue A", "clicuea")
    _cli_b, _ = _cliente_con_usuario(db, "Cliente Cue B", "clicueb")
    for _ in range(3):
        db.session.add(
            Notificacion(usuario_id=usuario_a.id, tipo="sistema",
                         titulo="Aviso", mensaje="m", leida=False)
        )
    db.session.add(
        Notificacion(usuario_id=_cli_b.usuario.id, tipo="sistema",
                     titulo="Aviso B", mensaje="m", leida=False)
    )
    db.session.commit()

    _login(client, "clicueb@test.com")
    datos = client.get("/notificaciones/api/listar").get_json()

    assert datos["no_leidas"] == 1
    assert [n["titulo"] for n in datos["items"]] == ["Aviso B"]


# ------------------------------------------------- asistente por rol


def test_asistente_no_expone_vehiculos_de_otros_a_clientes(app, db):
    """`recomendar_mantenimiento` consulta toda la flota: es de uso interno."""
    assert "recomendar_mantenimiento" in AssistantService.BUSINESS_ONLY

    cli, usuario = _cliente_con_usuario(db, "Cliente Bot", "clibot")
    db.session.add(
        Vehiculo(cliente_id=cli.id, placa="SEC999", marca="Ferrari", modelo="F430",
                 anio=2020, tipo="deportivo")
    )
    db.session.commit()

    respuesta = AssistantService.process_message(
        "recomienda mantenimiento Ferrari", usuario=usuario
    )
    assert "SEC999" not in respuesta.get("text", "")
