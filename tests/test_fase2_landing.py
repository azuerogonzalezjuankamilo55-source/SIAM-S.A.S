"""FASE 2 - Landing mejorado: sección de experiencia (mapa, asistencia, IA)."""
class TestLandingFase2:
    def test_landing_publica(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 302)
        if resp.status_code == 302:
            resp = client.get("/", follow_redirects=True)
            assert resp.status_code == 200

    def test_landing_muestra_seccion_experiencia(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "Nueva Experiencia" in html
        assert "Mapa de Sedes" in html
        assert "Asistencia en Emergencia" in html
        assert "Asistente IA" in html

    def test_landing_enlaza_a_sedes(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "sedes/" in html

    def test_landing_enlaza_al_asistente(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "asistente/" in html

    def test_landing_ancla_experiencia_en_nav(self, client):
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        assert "#experiencia" in html
