-- Create the dca_configurations table directly
DO $$ BEGIN
    CREATE TYPE entry_order_type_enum AS ENUM ('limit', 'market');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE take_profit_mode_enum AS ENUM ('per_leg', 'pyramid', 'aggregate', 'hybrid');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS dca_configurations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    pair VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    exchange VARCHAR NOT NULL,
    entry_order_type entry_order_type_enum NOT NULL DEFAULT 'limit',
    dca_levels JSON NOT NULL DEFAULT '[]'::json,
    tp_mode take_profit_mode_enum NOT NULL DEFAULT 'per_leg',
    tp_settings JSON NOT NULL DEFAULT '{}'::json,
    max_pyramids INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    CONSTRAINT uix_user_pair_timeframe_exchange UNIQUE (user_id, pair, timeframe, exchange)
);
