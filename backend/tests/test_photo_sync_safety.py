"""Isolated safety regression for photo sync, runnable without app DB dependencies."""
import ast
import asyncio
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'app/sync_engine/sync_service.py'

class Column:
    def __eq__(self, other):
        return ('eq', other)
    def is_(self, other):
        return ('is', other)
    def in_(self, other):
        return ('in', list(other))

class Employee:
    site_id = Column()
    is_manually_created = Column()
    personnel_code = Column()
    photo_thumbnail = Column()

class Query:
    def options(self, *args):
        return self
    def where(self, *args):
        return self

def load_method():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SyncService')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_sync_employee_photos')
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    env = {'select': lambda *args: Query(), 'undefer': lambda *args: None,
           'Employee': Employee, 'EmployeeMapping': object, 'logger': logging.getLogger('test.photo.sync')}
    exec(compile(module, str(SOURCE), 'exec'), env)
    return env['_sync_employee_photos']

class FakeDB:
    def __init__(self, employees):
        self.employees = employees
        self.queries = 0
        self.flushes = 0
    async def execute(self, query):
        self.queries += 1
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.employees))
    async def flush(self):
        self.flushes += 1

class PhotoSyncSafetyTests(unittest.TestCase):
    def setUp(self):
        self.method = load_method()
        self.mapping = SimpleNamespace(photo_table='EmployeeExtendedInfo',
          photo_emp_no_column='Emp_No',photo_thumbnail_column='ThumbnailImg')
    def run_sync(self, rows, employees):
        db = FakeDB(employees)
        adapter = SimpleNamespace(fetch_rows=self._async_rows(rows))
        asyncio.run(self.method(SimpleNamespace(db=db), 1, adapter, self.mapping))
        return db
    @staticmethod
    def _async_rows(rows):
        async def fetch_rows(*args):
            return rows
        return fetch_rows
    def test_empty_source_preserves_existing_photo(self):
        person = SimpleNamespace(personnel_code='101', photo_thumbnail=b'existing')
        db = self.run_sync([], [person])
        self.assertEqual(person.photo_thumbnail, b'existing')
        self.assertEqual(db.queries, 0)
    def test_null_row_does_not_erase_photo(self):
        person = SimpleNamespace(personnel_code='101', photo_thumbnail=b'existing')
        db = self.run_sync([{'Emp_No': '101', 'ThumbnailImg': None}], [person])
        self.assertEqual(person.photo_thumbnail, b'existing')
        self.assertEqual(db.queries, 0)
    def test_partial_source_updates_only_present_photo(self):
        present = SimpleNamespace(personnel_code='101', photo_thumbnail=b'old')
        missing = SimpleNamespace(personnel_code='102', photo_thumbnail=b'keep')
        db = self.run_sync([{'Emp_No': '101', 'ThumbnailImg': b'new'}], [present, missing])
        self.assertEqual(present.photo_thumbnail, b'new')
        self.assertEqual(missing.photo_thumbnail, b'keep')
        self.assertEqual(db.flushes, 1)

if __name__ == '__main__':
    unittest.main()
