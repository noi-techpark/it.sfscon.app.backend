from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" ADD "rateable" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "conferences_event_sessions" ADD "bookmarkable" BOOL NOT NULL  DEFAULT True;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" DROP COLUMN "rateable";
        ALTER TABLE "conferences_event_sessions" DROP COLUMN "bookmarkable";"""
