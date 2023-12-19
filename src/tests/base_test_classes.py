# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import pytest
import dotenv
import logging
import psycopg2
import importlib
from tortoise import Tortoise
from abc import ABC, abstractmethod

from app import startup_event, shutdown_event, get_app

logging.disable(logging.CRITICAL)
dotenv.load_dotenv()
os.environ["TEST_MODE"] = "true"


class BaseAPITest(ABC):
    app = None

    def import_modules(self, svcs):
        for svc in svcs:
            importlib.reload(importlib.import_module(svc))

        self.app = get_app()

    @abstractmethod
    async def setup(self):
        ...

    @pytest.fixture(autouse=True, scope="function")
    async def setup_fixture(self):
        await startup_event()
        try:
            await self.setup()
        except Exception as e:
            raise
        try:
            yield
        except Exception as e:
            raise

        await shutdown_event()


class BaseTest:

    @pytest.fixture(autouse=True)
    async def automatic_fixture(self):
        await self.async_setup()
        yield
        await self.async_teardown()

    @staticmethod
    async def helper_drop(test_db):

        terminate_sessions_sql = f"""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = '{test_db}'
                        AND pid <> pg_backend_pid();
                        """

        conn = psycopg2.connect(user=os.getenv('DB_USERNAME'), password=os.getenv('DB_PASSWORD'), database='template1', host='localhost')
        conn.autocommit = True

        cur = conn.cursor()
        cur.execute(terminate_sessions_sql)

        try:
            cur.execute(f"DROP DATABASE IF EXISTS {test_db}")
            cur.execute(f"CREATE DATABASE {test_db}")
            cur.close()
            conn.close()
        except Exception as e:
            raise

    @staticmethod
    async def async_setup():
        test_pfx = 'test_'
        test_db_name = f"{test_pfx}{os.getenv('DB_NAME')}"
        try:
            await BaseTest.helper_drop(test_db_name)
        except Exception as e:
            pass
        try:
            await Tortoise.init(
                db_url=f"postgres://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{test_db_name}",
                modules={"models": ["conferences.models"]},
                use_tz=True,
                timezone='CET',
            )
        except Exception as e:
            raise

        try:
            await Tortoise.generate_schemas()
        except Exception as e:
            raise

    @staticmethod
    async def async_teardown():
        await Tortoise.close_connections()
