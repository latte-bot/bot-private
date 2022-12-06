CREATE TABLE IF NOT EXISTS riot_accounts(
    user_id BIGINT NOT NULL,
    guild_id BIGINT,
    extras VARCHAR,
    date_signed TIMESTAMP,
    locale VARCHAR
);