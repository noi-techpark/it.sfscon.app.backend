from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "conferences" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "acronym" TEXT,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "last_updated" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "source_uri" TEXT
);
CREATE TABLE IF NOT EXISTS "conferences_lecturers" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "slug" VARCHAR(255) NOT NULL,
    "external_id" VARCHAR(255) NOT NULL,
    "display_name" TEXT NOT NULL,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL,
    "email" TEXT,
    "thumbnail_url" TEXT,
    "bio" TEXT,
    "organization" TEXT,
    "social_networks" JSONB,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_conferences_slug_4860af" ON "conferences_lecturers" ("slug");
CREATE INDEX IF NOT EXISTS "idx_conferences_externa_b43bc9" ON "conferences_lecturers" ("external_id");
CREATE TABLE IF NOT EXISTS "conferences_entrances" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_locations" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_pretix_orders" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "id_pretix_order" VARCHAR(32) NOT NULL,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT,
    "organization" TEXT,
    "email" TEXT,
    "secret" TEXT NOT NULL,
    "secret_per_sub_event" JSONB,
    "push_notification_token" VARCHAR(64),
    "registered_in_open_con_app" BOOL,
    "registered_from_device_type" VARCHAR(32),
    "nr_printed_labels" INT NOT NULL  DEFAULT 0,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_id_pret_f96b97" UNIQUE ("id_pretix_order", "conference_id")
);
CREATE INDEX IF NOT EXISTS "idx_conferences_id_pret_9ce4b0" ON "conferences_pretix_orders" ("id_pretix_order");
CREATE INDEX IF NOT EXISTS "idx_conferences_registe_7734f1" ON "conferences_pretix_orders" ("registered_from_device_type");
CREATE TABLE IF NOT EXISTS "conferences_pretix_qr_scans" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "pretix_secret" TEXT NOT NULL,
    "label_print_confirmed" BOOL NOT NULL  DEFAULT False,
    "label_printed" TIMESTAMPTZ,
    "pretix_order_id" UUID REFERENCES "conferences_pretix_orders" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_push_notification_queue" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "sent" TIMESTAMPTZ,
    "attempt" INT NOT NULL  DEFAULT 0,
    "last_response" TEXT,
    "subject" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "pretix_order_id" UUID NOT NULL REFERENCES "conferences_pretix_orders" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_rooms" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE,
    "location_id" UUID NOT NULL REFERENCES "conferences_locations" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_tracks" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "color" TEXT NOT NULL,
    "order" INT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_event_sessions" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "unique_id" VARCHAR(255) NOT NULL,
    "title" TEXT NOT NULL,
    "duration" INT,
    "abstract" TEXT,
    "description" TEXT,
    "start_date" TIMESTAMPTZ NOT NULL,
    "end_date" TIMESTAMPTZ NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE,
    "room_id" UUID NOT NULL REFERENCES "conferences_rooms" ("id") ON DELETE CASCADE,
    "track_id" UUID NOT NULL REFERENCES "conferences_tracks" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_unique__0ced27" UNIQUE ("unique_id", "conference_id")
);
CREATE TABLE IF NOT EXISTS "conferences_bookmarks" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "event_session_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE,
    "pretix_order_id" UUID NOT NULL REFERENCES "conferences_pretix_orders" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_pretix__d82808" UNIQUE ("pretix_order_id", "event_session_id")
);
CREATE TABLE IF NOT EXISTS "conferences_stars" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "stars" INT NOT NULL,
    "event_session_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE,
    "pretix_order_id" UUID NOT NULL REFERENCES "conferences_pretix_orders" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_pretix__b745a6" UNIQUE ("pretix_order_id", "event_session_id")
);
CREATE TABLE IF NOT EXISTS "conferences_starred_sessions" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "nr_votes" INT NOT NULL,
    "total_stars" INT NOT NULL,
    "avg_stars" DECIMAL(3,2) NOT NULL,
    "event_session_id" UUID NOT NULL UNIQUE REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_conferences_event_s_dd527c" ON "conferences_starred_sessions" ("event_session_id");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "conferences_lecturers_conferences_event_sessions" (
    "conferences_lecturers_id" UUID NOT NULL REFERENCES "conferences_lecturers" ("id") ON DELETE CASCADE,
    "eventsession_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
