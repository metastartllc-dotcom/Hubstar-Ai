import sqlite3
import pytest
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from app.core.database import Base

ROOT = Path(__file__).parents[1]
COLUMN = "included_delivery_one_way_distance_km"
LINK_TABLE = "work_equipment_links"

def config(path):
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", "sqlite:///" + path.as_posix())
    return cfg

def old_schema(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE projects(id INTEGER PRIMARY KEY, project_id VARCHAR UNIQUE, name VARCHAR NOT NULL);
        CREATE TABLE work_items(id INTEGER PRIMARY KEY, work_id VARCHAR UNIQUE, project_id INTEGER REFERENCES projects(id), name VARCHAR NOT NULL);
        CREATE TABLE materials(id INTEGER PRIMARY KEY, material_id VARCHAR UNIQUE, name VARCHAR NOT NULL);
        CREATE TABLE work_material_links(id INTEGER PRIMARY KEY, work_id INTEGER REFERENCES work_items(id), material_id INTEGER REFERENCES materials(id));
        CREATE TABLE equipments(id INTEGER PRIMARY KEY, equipment_id VARCHAR UNIQUE, type VARCHAR);
        CREATE TABLE transports(id INTEGER PRIMARY KEY, transport_id VARCHAR UNIQUE);
        INSERT INTO projects VALUES(1,'P','Project'); INSERT INTO work_items VALUES(1,'W',1,'Work');
        INSERT INTO materials VALUES(1,'M','Material'); INSERT INTO work_material_links VALUES(1,1,1);
        INSERT INTO equipments VALUES(1,'E','Crane');
        """)

def test_upgrade_existing_data_repeat_and_round_trip(tmp_path):
    path = tmp_path / "old.db"; old_schema(path); cfg = config(path)
    with sqlite3.connect(path) as db:
        before_data = {t: db.execute(f'SELECT * FROM "{t}"').fetchall()
                       for t in ("projects", "work_items", "materials", "work_material_links", "equipments")}
        before_fks = {t: db.execute(f'PRAGMA foreign_key_list("{t}")').fetchall()
                      for t in before_data}
        before_indexes = {t: db.execute(f'PRAGMA index_list("{t}")').fetchall()
                          for t in before_data}
    command.upgrade(cfg, "head"); command.upgrade(cfg, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("select version_num from alembic_version").fetchone()[0] == "0003_work_equipment_links"
        assert db.execute("select equipment_id,type," + COLUMN + " from equipments").fetchone() == ("E", "Crane", None)
        assert db.execute("select count(*) from work_material_links").fetchone()[0] == 1
        assert COLUMN in {r[1] for r in db.execute("pragma table_info(equipments)")}
        assert {t: db.execute(f'SELECT * FROM "{t}"').fetchall() for t in before_data} == {
            **before_data, "equipments": [(1, "E", "Crane", None)]}
        assert {t: db.execute(f'PRAGMA foreign_key_list("{t}")').fetchall() for t in before_data} == before_fks
        assert {t: db.execute(f'PRAGMA index_list("{t}")').fetchall() for t in before_data} == before_indexes
    command.downgrade(cfg, "0001_existing_schema")
    with sqlite3.connect(path) as db:
        assert COLUMN not in {r[1] for r in db.execute("pragma table_info(equipments)")}
    command.upgrade(cfg, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("select equipment_id,type from equipments").fetchall() == [("E", "Crane")]
        assert {t: db.execute(f'PRAGMA foreign_key_list("{t}")').fetchall() for t in before_data} == before_fks
        assert {t: db.execute(f'PRAGMA index_list("{t}")').fetchall() for t in before_data} == before_indexes

def test_fresh_create_all_upgrade_is_compatible_and_import_is_passive(tmp_path):
    path = tmp_path / "fresh.db"; engine = create_engine("sqlite:///" + path.as_posix())
    Base.metadata.create_all(engine); engine.dispose()
    before = path.stat().st_size
    __import__("app.api.main")
    assert "alembic_version" not in inspect(create_engine("sqlite:///" + path.as_posix())).get_table_names()
    command.upgrade(config(path), "head"); command.upgrade(config(path), "head")
    engine = create_engine("sqlite:///" + path.as_posix())
    assert COLUMN in {c["name"] for c in inspect(engine).get_columns("equipments")}
    assert engine.connect().execute(text("select version_num from alembic_version")).scalar() == "0003_work_equipment_links"
    engine.dispose(); assert path.stat().st_size >= before


def test_completely_empty_database_fails_clearly_without_false_head(tmp_path):
    path = tmp_path / "empty.db"; sqlite3.connect(path).close()
    with pytest.raises(RuntimeError, match="Existing schema is incomplete.*init_db"):
        command.upgrade(config(path), "head")
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT version_num FROM alembic_version").fetchone()
        assert row is None
        assert "equipments" not in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_work_equipment_migration_contract_and_round_trip(tmp_path):
    path = tmp_path / "links.db"; old_schema(path); cfg = config(path)
    command.upgrade(cfg, "head")
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        columns = {r[1]: r for r in db.execute(f"pragma table_info({LINK_TABLE})")}
        assert {"work_item_id", "equipment_id", "usage_quantity"}.issubset(columns)
        assert columns["usage_quantity"][3] == 1
        indexes = {r[1] for r in db.execute(f"pragma index_list({LINK_TABLE})")}
        assert {"ix_work_equipment_links_id", "ix_work_equipment_links_work_item_id", "ix_work_equipment_links_equipment_id"}.issubset(indexes)
        db.execute(f"insert into {LINK_TABLE}(work_item_id,equipment_id,usage_quantity) values(1,1,72)")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"insert into {LINK_TABLE}(work_item_id,equipment_id,usage_quantity) values(1,1,1)")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"insert into {LINK_TABLE}(work_item_id,equipment_id,usage_quantity) values(999,1,1)")
    command.downgrade(cfg, "0002_equipment_delivery_distance")
    with sqlite3.connect(path) as db:
        assert LINK_TABLE not in {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
        assert db.execute("select count(*) from work_items").fetchone()[0] == 1
    command.upgrade(cfg, "head")


def test_malformed_existing_work_equipment_table_fails(tmp_path):
    path = tmp_path / "bad.db"; old_schema(path); cfg = config(path)
    command.upgrade(cfg, "0002_equipment_delivery_distance")
    with sqlite3.connect(path) as db:
        db.execute("create table work_equipment_links(id integer primary key)")
    with pytest.raises(RuntimeError, match="incompatible column contract"):
        command.upgrade(cfg, "head")
