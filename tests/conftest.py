import pytest
from app import create_app
from database.db import db as _db
from sqlalchemy import text


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.close()
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    return _db


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True, scope="function")
def _clean_db(app):
    yield
    with app.app_context():
        _db.session.execute(text("PRAGMA foreign_keys = OFF"))
        for table in _db.metadata.sorted_tables:
            _db.session.execute(table.delete())
        _db.session.execute(text("PRAGMA foreign_keys = ON"))
        _db.session.commit()
