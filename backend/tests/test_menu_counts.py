"""Run the production aggregate against representative multi-site queues."""
import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine

from app.services.menu_counts import pending_menu_counts


def test_menu_counts_follow_action_and_permission_scope():
    with create_engine("sqlite://").connect() as conn:
        schema = {
            "sites": "id", "employees": "id, site_id, is_active", "users": "id, employee_id",
            "family_profiles": "id, employee_id, status", "career_applications": "id, status",
            "loan_requests": "id, site_id, status", "advance_requests": "id, site_id, status",
            "feedback_messages": "id, sender_id, status, is_deleted",
            "feedback_replies": "id, feedback_id, created_at, is_from_sender",
            "permissions": "id, code", "role_permissions": "role_id, permission_id",
            "user_permissions": "user_id, permission_id, site_id", "user_roles": "user_id, role_id, site_id",
        }
        for table, columns in schema.items():
            conn.exec_driver_sql(f"CREATE TABLE {table} ({columns})")
        data = {
            "sites": "(1),(2)", "employees": "(1,1,1),(2,2,1),(3,1,0)",
            "users": "(1,1),(2,2),(3,null)",
            "family_profiles": "(1,1,'pending'),(2,2,'pending'),(3,3,'pending')",
            "career_applications": "(1,'new'),(2,'accepted')",
            "loan_requests": "(1,1,'waiting_finance'),(2,2,'waiting_finance'),(3,1,'active')",
            "advance_requests": "(1,1,'waiting_finance'),(2,1,'approved'),(3,1,'paid')",
            "feedback_messages": "(1,1,'new',0),(2,1,'answered',0),(3,1,'answered',0),(4,1,'closed',0),"
                                 "(5,1,'new',1),(6,3,'new',0)",
            "feedback_replies": "(1,2,1,0),(2,3,1,0),(3,3,1,1)",
            "permissions": "(1,'family.manage'),(2,'careers.manage'),(3,'loans.finance'),"
                           "(4,'advances.finance'),(5,'feedback.reply')",
            "role_permissions": "(1,1),(1,3),(1,4),(1,5)",
            "user_roles": "(7,1,1)", "user_permissions": "(7,2,1),(7,2,2)",
        }
        for table, rows in data.items():
            conn.exec_driver_sql(f"INSERT INTO {table} VALUES {rows}")

        class DB:
            async def execute(self, statement):
                return conn.execute(statement)

        def counts(uid, admin=False):
            return asyncio.run(pending_menu_counts(DB(), SimpleNamespace(id=uid, is_superuser=admin)))

        assert counts(9) == {}
        assert counts(7) == dict(family=1, loans=1, advances=2, feedback=2)
        assert counts(7, True) == dict(careers=1, family=2, loans=2, advances=2, feedback=3)
        conn.exec_driver_sql("INSERT INTO user_permissions VALUES (7,2,null),(7,5,2)")
        conn.exec_driver_sql("UPDATE family_profiles SET status='approved' WHERE employee_id=1")
        conn.exec_driver_sql("UPDATE advance_requests SET status='paid' WHERE id=2")
        assert counts(7) == dict(careers=1, family=0, loans=1, advances=1, feedback=3)
