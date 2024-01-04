from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" ADD "notification5min_sent" BOOL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_event_sessions" DROP COLUMN "notification5min_sent";"""
