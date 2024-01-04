from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "conferences_flows" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "text" TEXT,
    "data" JSONB,
    "conference_id" UUID REFERENCES "conferences" ("id") ON DELETE CASCADE,
    "pretix_order_id" UUID REFERENCES "conferences_pretix_orders" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_conferences_confere_a4c04b" ON "conferences_flows" ("conference_id");
CREATE INDEX IF NOT EXISTS "idx_conferences_pretix__050ab5" ON "conferences_flows" ("pretix_order_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "conferences_flows";"""
