CREATE TABLE IF NOT EXISTS riot_accounts(
    user_id BIGINT NOT NULL,
    guild_id BIGINT,
    extras VARCHAR,
    date_signed TIMESTAMP,
    locale VARCHAR
);

CREATE TABLE IF NOT EXISTS blacklisted(
    snowflake BIGINT NOT NULL,
    reason VARCHAR,
    date_added TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_commands_stats(
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    uses INT NOT NULL
);