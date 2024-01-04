from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "organization" TYPE VARCHAR(255) USING "organization"::VARCHAR(255);
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "first_name" DROP NOT NULL;
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "first_name" TYPE VARCHAR(255) USING "first_name"::VARCHAR(255);
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "last_name" TYPE VARCHAR(255) USING "last_name"::VARCHAR(255);
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "email" TYPE VARCHAR(255) USING "email"::VARCHAR(255);
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "organization" TYPE TEXT USING "organization"::TEXT;
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "first_name" TYPE TEXT USING "first_name"::TEXT;
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "first_name" SET NOT NULL;
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "last_name" TYPE TEXT USING "last_name"::TEXT;
        ALTER TABLE "conferences_pretix_orders" ALTER COLUMN "email" TYPE TEXT USING "email"::TEXT;"""
