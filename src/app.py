# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import logging
import uuid

import psycopg2
from fastapi import FastAPI
from fastapi import Depends
from tortoise import Tortoise
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

from db_config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield
    await shutdown_event()


async def startup_event():
    logger.info("Starting up...")

    test_mode = os.getenv("TEST_MODE", "false").lower() == "true"

    test_mode_pfx = 'test_' if test_mode else ''

    db_name = f"{test_mode_pfx}{os.getenv('DB_NAME')}"

    db_url = f"postgres://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{db_name}"

    if test_mode:
        terminate_sessions_sql = f"""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = '{db_name}'
                          AND pid <> pg_backend_pid();
                        """

        conn = psycopg2.connect(user=os.getenv('DB_USERNAME'), password=os.getenv('DB_PASSWORD'), database='template1', host=os.getenv('DB_HOST'))

        conn.autocommit = True

        cur = conn.cursor()

        # Terminate active sessions
        cur.execute(terminate_sessions_sql)

        cur.execute(f'DROP DATABASE IF EXISTS {db_name}')

        # Create a new database
        cur.execute(f'CREATE DATABASE {db_name}')

        cur.close()
        conn.close()

    # Initialize Tortoise ORM
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["conferences.models"]}  # Assuming models.py is in the same directory
    )

    # Generate the database schema
    try:
        await Tortoise.generate_schemas()
    except Exception as e:
        raise
    ...

    # if os.getenv('TEST_MODE', 'false').lower() == 'true':
    #     yield
    #     await Tortoise.close_connections()


async def test_dependency_startup():
    if os.getenv('TEST_MODE', 'false').lower() == 'true':
        await startup_event()
        yield
        await shutdown_event()
    else:
        yield


async def shutdown_event():
    logger.info("Shutting down...")
    await Tortoise.close_connections()


def get_app():
    if not hasattr(get_app, 'app'):
        get_app.app = FastAPI(lifespan=lifespan)

    return get_app.app

# app = get_app()
