from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" ADD "str_start_date_local" VARCHAR(20);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" DROP COLUMN "str_start_date_local";"""
