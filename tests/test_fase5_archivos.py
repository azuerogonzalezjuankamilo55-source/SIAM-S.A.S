"""FASE 5 - Archivos seguros: FileService, Adjunto y portal de documentos."""
import io
import os

from models import Usuario, Adjunto
from services.storage_service import FileService, FileError, AdjuntoService


def _crear_cliente(db):
    u = Usuario(nombre="Cliente", correo="cli_files@test.com", rol="cliente")
    u.set_password("clave1234")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, correo="cli_files@test.com", password="clave1234"):
    return client.post("/auth/login", data={
        "correo": correo,
        "password": password,
    }, follow_redirects=True)


def _stream_bytes(data: bytes, filename: str, mime: str):
    from werkzeug.datastructures import FileStorage
    return FileStorage(stream=io.BytesIO(data), filename=filename, content_type=mime)


class TestFileServiceValidacion:
    def test_detectar_tipo(self):
        assert FileService.detectar_tipo("foto.jpg", "image/jpeg") == "imagen"
        assert FileService.detectar_tipo("video.mp4", "video/mp4") == "video"
        assert FileService.detectar_tipo("doc.pdf", "application/pdf") == "pdf"
        assert FileService.detectar_tipo("evil.exe", "application/x-msdownload") is None

    def test_extension_invalida(self):
        with pytest.raises(FileError):
            FileService.validar("pdf", _stream_bytes(b"data", "doc.txt", "text/plain"))

    def test_vacio_rechazado(self):
        with pytest.raises(FileError):
            FileService.validar("pdf", _stream_bytes(b"", "doc.pdf", "application/pdf"))

    def test_mime_invalido(self):
        with pytest.raises(FileError):
            FileService.validar("video", _stream_bytes(b"data", "clip.mp4", "text/html"))


class TestFileServiceGuardado:
    def test_guardar_pdf_y_eliminar(self, app):
        with app.app_context():
            pdf = _stream_bytes(b"%PDF-1.4 test", "soporte.pdf", "application/pdf")
            ruta = FileService.guardar("pdf", pdf, "pruebas")
            assert ruta.startswith("/static/uploads/pruebas/")
            assert ruta.endswith(".pdf")
            abs_path = FileService._ruta_abs(ruta)
            assert abs_path and os.path.isfile(abs_path)
            FileService.eliminar(ruta)
            assert not os.path.isfile(abs_path)


class TestAdjuntoService:
    def test_crear_y_listar_por_usuario(self, app, db):
        with app.app_context():
            u = _crear_cliente(db)
            pdf = _stream_bytes(b"%PDF-1.4 test", "factura.pdf", "application/pdf")
            adj = AdjuntoService.crear(u, "pdf", pdf, entidad_tipo="cita", entidad_id=5, subcarpeta="pruebas")
            assert adj.id is not None
            assert adj.nombre_original == "factura.pdf"
            assert adj.tamano_legible
            items = AdjuntoService.listar(u.id)
            assert len(items) == 1
            assert items[0].es_pdf
            adj_path = FileService._ruta_abs(adj.path)
            assert adj_path and os.path.isfile(adj_path)
            adj_id = adj.id
            AdjuntoService.eliminar(u.id, adj_id)
            assert db.session.get(Adjunto, adj_id) is None

    def test_eliminar_ajeno_no_funciona(self, app, db):
        with app.app_context():
            u1 = _crear_cliente(db)
            u2 = Usuario(nombre="Otro", correo="otro_files@test.com", rol="cliente")
            u2.set_password("clave1234")
            db.session.add(u2)
            db.session.commit()
            pdf = _stream_bytes(b"%PDF-1.4 test", "privado.pdf", "application/pdf")
            adj = AdjuntoService.crear(u1, "pdf", pdf, subcarpeta="pruebas")
            adj_id = adj.id
            assert AdjuntoService.eliminar(u2.id, adj_id) is False
            assert db.session.get(Adjunto, adj_id) is not None


class TestPortalDocumentos:
    def test_pagina_requiere_login(self, client):
        resp = client.get("/portal/documentos")
        assert resp.status_code in (401, 302)

    def test_pagina_lista(self, client, app, db):
        with app.app_context():
            u = _crear_cliente(db)
        _login(client)
        resp = client.get("/portal/documentos")
        assert resp.status_code == 200
        assert b"Mis Documentos" in resp.data

    def test_adjuntar_y_descargar(self, client, app, db):
        with app.app_context():
            u = _crear_cliente(db)
        _login(client)
        data = {
            "csrf_token": "",
            "archivo": (io.BytesIO(b"%PDF-1.4 test"), "soporte.pdf"),
        }
        resp = client.post("/portal/documentos/adjuntar", data=data,
                           content_type="multipart/form-data", follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            adj = Adjunto.query.first()
            assert adj is not None
            assert adj.nombre_original == "soporte.pdf"
            resp = client.get(f"/portal/documentos/descargar/{adj.id}")
            assert resp.status_code == 200
            assert b"%PDF-1.4" in resp.data

    def test_no_puede_ver_ajeno(self, client, app, db):
        with app.app_context():
            u1 = _crear_cliente(db)
            u2 = Usuario(nombre="Otro", correo="otro2@test.com", rol="cliente")
            u2.set_password("clave1234")
            db.session.add(u2)
            db.session.commit()
            pdf = _stream_bytes(b"%PDF-1.4 test", "secreto.pdf", "application/pdf")
            adj = AdjuntoService.crear(u1, "pdf", pdf, subcarpeta="pruebas")
            adj_id = adj.id
        _login(client, "otro2@test.com")
        resp = client.get(f"/portal/documentos/descargar/{adj_id}")
        assert resp.status_code == 302
        assert b"secreto.pdf" not in resp.data

    def test_solicitar_cita_con_adjunto(self, client, app, db):
        from models import Cliente, Vehiculo
        with app.app_context():
            u = _crear_cliente(db)
            cli = Cliente(nombre="Cliente Files")
            db.session.add(cli)
            db.session.flush()
            u.cliente_id = cli.id
            v = Vehiculo(placa="ABC123", marca="Kia", modelo="Picanto", cliente_id=cli.id)
            db.session.add(v)
            db.session.commit()
            vid = v.id
        _login(client)
        resp = client.post("/portal/citas/solicitar", data={
            "vehiculo_id": str(vid),
            "sede_id": "1",
            "fecha": "2026-09-01",
            "hora": "10:30",
            "descripcion": "Ruido en frenos",
            "adjuntos": (io.BytesIO(b"%PDF-1.4 test"), "ruido.pdf"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            adj = Adjunto.query.filter_by(entidad_tipo="cita").first()
            assert adj is not None
            assert adj.entidad_id is not None


import pytest
