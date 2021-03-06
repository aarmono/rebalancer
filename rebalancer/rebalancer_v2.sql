PRAGMA foreign_keys=OFF;

BEGIN TRANSACTION;

CREATE TABLE TargetTypes
(
    ID           INTEGER NOT NULL PRIMARY KEY,
    Name         TEXT    NOT NULL UNIQUE,
    Abbreviation VARCHAR(16) NOT NULL UNIQUE,

    CHECK (LENGTH(Name) > 0),
    CHECK (LENGTH(Abbreviation) > 0)
);

INSERT INTO TargetTypes (Name, Abbreviation) VALUES ("Percent", "%");
INSERT INTO TargetTypes (Name, Abbreviation) VALUES ("Dollars", "$");
-- For portfolios which use a fixed dollar target or fixed percentage targets
-- which do not add up to 100%, this is the percent the remainder of the
-- portfolio value after computing the target values from the fixed percentage
-- and fixed dollar allocations
INSERT INTO TargetTypes (Name, Abbreviation) VALUES ("Percent Remainder", "% Remainder");

CREATE TABLE Targets_V2
(
    User       TEXT    NOT NULL,
    AssetID    INTEGER NOT NULL,
    Target     INTEGER NOT NULL,
    TargetType INTEGER NOT NULL,

    FOREIGN KEY("AssetID")    REFERENCES Assets("ID")      ON DELETE CASCADE,
    FOREIGN KEY("TargetType") REFERENCES TargetTypes("ID") ON DELETE CASCADE,

    CONSTRAINT AssetUniqueByUser PRIMARY KEY (User, AssetID)
) WITHOUT ROWID;

INSERT INTO
    Targets_V2 (User, AssetID, Target, TargetType)
SELECT
    User, AssetID, TargetDeciPercent, (SELECT ID FROM TargetTypes WHERE Name == "Percent")
FROM
    Targets;

DROP TABLE Targets;
ALTER TABLE Targets_V2 RENAME TO Targets;

DROP VIEW AssetTargetsMap;

CREATE VIEW AssetTargetsMap
AS
SELECT
    Targets.User        AS "User",
    Assets.Abbreviation AS "Asset",
    Targets.Target      AS "Target",
    TargetTypes.Name    AS "TargetType"
FROM
    Targets
INNER JOIN
    Assets ON Targets.AssetID == Assets.ID
INNER JOIN
    TargetTypes ON Targets.TargetType == TargetTypes.ID
;

PRAGMA foreign_key_check;
PRAGMA user_version=2;

COMMIT;

PRAGMA foreign_keys=ON;