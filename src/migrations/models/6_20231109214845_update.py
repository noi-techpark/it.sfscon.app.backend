# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" RENAME COLUMN "str_start_date_local" TO "str_start_time";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" RENAME COLUMN "str_start_time" TO "str_start_date_local";"""
