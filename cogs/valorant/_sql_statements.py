from typing import Final

CREATE_TABLE: Final[
    str
] = """
CREATE TABLE IF NOT EXISTS riot_accounts (
    user_id BIGINT PRIMARY KEY,
    guild_id BIGINT,
    extras VARCHAR(4096),
    date_signed TIMESTAMP,
    locale VARCHAR(100));
"""

ACCOUNT_INSERT_OR_UPDATE: Final[
    str
] = """
INSERT 
INTO
    riot_accounts
    (user_id, guild_id, extras, date_signed)     
VALUES
    ($1, $2, $3, $4)     
        ON CONFLICT (user_id) DO UPDATE
            
    SET
        guild_id = $2,
        extras = $3,
        date_signed = $4,
        locale = $5;
"""

ACCOUNT_UPSERT: Final[
    str
] = """
   WITH upsert AS (UPDATE
    riot_accounts 
SET
    user_id = $1,
    guild_id = $2,
    extras = $3,
    date_signed = $4,
    locale = $5
WHERE
    user_id = $6 RETURNING *) INSERT 
    INTO
        riot_accounts
        (user_id, guild_id, extras, date_signed, locale) SELECT
            $1,
            $2,
            $3,
            $4,
            $5
        WHERE
            NOT EXISTS (
                SELECT
                    * 
                FROM
                    upsert
            );
"""

ACCOUNT_UPDATE_EXTRAS: Final[
    str
] = """
UPDATE
    riot_accounts 
SET
    extras = $1 
WHERE
    user_id = $2;
"""

ACCOUNT_DELETE: Final[
    str
] = """
DELETE 
FROM
    riot_accounts 
WHERE
    user_id = $1
RETURNING *;
"""

ACCOUNT_SELECT: Final[
    str
] = """
SELECT
    *
FROM
    riot_accounts
WHERE
    user_id = $1;
"""

ACCOUNT_SELECT_ALL: Final[
    str
] = """
SELECT
    *
FROM
    riot_accounts;
"""

ACCOUNT_DELETE_BY_GUILD: Final[
    str
] = """
DELETE 
FROM
    riot_accounts 
WHERE
    guild_id = $1 RETURNING user_id;"""
