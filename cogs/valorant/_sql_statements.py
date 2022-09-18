from typing import Final

RIOT_ACC_CREATE_TABLE: Final[
    str
] = """
CREATE TABLE IF NOT EXISTS riot_accounts (
    user_id BIGINT PRIMARY KEY,
    guild_id BIGINT,
    extras VARCHAR(4096),
    date_signed TIMESTAMP);
"""

RIOT_ACC_INSERT_OR_UPDATE: Final[
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
        date_signed = $4;
"""

RIOT_ACC_WITH_UPSERT: Final[
    str
] = """
   WITH upsert AS (UPDATE
    riot_accounts 
SET
    user_id = $1,
    guild_id = $2,
    extras = $3,
    date_signed = $4 
WHERE
    user_id = $5 RETURNING *) INSERT 
    INTO
        riot_accounts
        (user_id, guild_id,       extras, date_signed) SELECT
            $1,
            $2,
            $3,
            $4 
        WHERE
            NOT EXISTS (
                SELECT
                    * 
                FROM
                    upsert
            );
"""

RIOT_ACC_UPDATE_EXTRAS: Final[
    str
] = """
UPDATE
    riot_accounts 
SET
    extras = $1 
WHERE
    user_id = $2;
"""

RIOT_ACC_DELETE: Final[
    str
] = """
DELETE 
FROM
    riot_accounts 
WHERE
    user_id = $1;
"""

RIOT_ACC_SELECT: Final[
    str
] = """
SELECT
    *
FROM
    riot_accounts
WHERE
    user_id = $1;
"""

RIOT_ACC_SELECT_ALL: Final[
    str
] = """
SELECT
    *
FROM
    riot_accounts;
"""

RIOT_ACC_DELETE_BY_GUILD: Final[
    str
] = """
DELETE 
FROM
    riot_accounts 
WHERE
    guild_id = $1 RETURNING user_id;"""
