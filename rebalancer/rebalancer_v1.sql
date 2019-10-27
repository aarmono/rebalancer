BEGIN TRANSACTION;

CREATE TABLE AssetGroups
(
    ID   INTEGER PRIMARY KEY,
    Name TEXT    NOT NULL UNIQUE
);

CREATE TABLE TaxGroups
(
    ID   INTEGER PRIMARY KEY,
    Name TEXT    NOT NULL UNIQUE
);

CREATE TABLE Assets
(
    ID           INTEGER     PRIMARY KEY,
    AssetGroupID INTEGER     NOT NULL,
    Abbreviation VARCHAR(16) NOT NULL UNIQUE,

    FOREIGN KEY("AssetGroupID") REFERENCES AssetGroups("ID") ON DELETE CASCADE
);

CREATE TABLE Securities
(
    Symbol  VARCHAR(8) NOT NULL PRIMARY KEY,
    AssetID INTEGER    NOT NULL,

    FOREIGN KEY("AssetID") REFERENCES Assets("ID") ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE UserSalts
(
    User TEXT     NOT NULL PRIMARY KEY,
    Salt CHAR(32) NOT NULL DEFAULT (HEX(RANDOMBLOB(16))),

    CHECK (LENGTH(Salt) == 32)
) WITHOUT ROWID;

CREATE TABLE Targets
(
    User              TEXT     NOT NULL,
    AssetID           INTEGER  NOT NULL,
    TargetDeciPercent INTEGER  NOT NULL,

    FOREIGN KEY("AssetID") REFERENCES Assets("ID") ON DELETE CASCADE,

    CONSTRAINT AssetUniqueByUser PRIMARY KEY (User, AssetID)
);

CREATE TABLE Accounts
(
    ID          TEXT     NOT NULL PRIMARY KEY,
    Description TEXT              DEFAULT NULL,
    TaxGroupID  INTEGER  NOT NULL,

    FOREIGN KEY("TaxGroupID") REFERENCES TaxGroups("ID") ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE AssetAffinities
(
    User       TEXT    NOT NULL,
    AssetID    INTEGER NOT NULL,
    TaxGroupID INTEGER NOT NULL,
    Priority   INTEGER NOT NULL,

    FOREIGN KEY("AssetID")    REFERENCES Assets("ID") ON DELETE CASCADE,
    FOREIGN KEY("TaxGroupID") REFERENCES TaxGroups("ID") ON DELETE CASCADE,

    CONSTRAINT RowUniqueness PRIMARY KEY (User, AssetID, TaxGroupID)
);

CREATE VIEW AssetGroupsMap
AS
SELECT
    Assets.Abbreviation AS "Asset",
    AssetGroups.Name    AS "AssetGroup"
FROM
    Assets
INNER JOIN
    AssetGroups ON Assets.AssetGroupID == AssetGroups.ID
;

CREATE VIEW SecuritiesMap
AS
SELECT
    Securities.Symbol   AS "Symbol",
    Assets.Abbreviation AS "Asset",
    AssetGroups.Name    AS "AssetGroup"
FROM
    Securities
INNER JOIN
    Assets ON Securities.AssetID == Assets.ID
INNER JOIN
    AssetGroups ON Assets.AssetGroupID == AssetGroups.ID
;

CREATE VIEW AccountInfoMap
AS
SELECT
    Accounts.ID          AS "AccountID",
    Accounts.Description AS "Description",
    TaxGroups.Name       AS "TaxGroup"
FROM
    Accounts
INNER JOIN
    TaxGroups ON Accounts.TaxGroupID == TaxGroups.ID
;

CREATE VIEW AssetAffinitiesMap
AS
SELECT
    AssetAffinities.User     AS "User",
    Assets.Abbreviation      AS "Asset",
    TaxGroups.Name           AS "TaxGroup",
    AssetAffinities.Priority AS "Priority"
FROM
    AssetAffinities
INNER JOIN
    Assets ON AssetAffinities.AssetID == Assets.ID
INNER JOIN
    TaxGroups ON AssetAffinities.TaxGroupID == TaxGroups.ID
;

CREATE VIEW AssetTargetsMap
AS
SELECT
    Targets.User              AS "User",
    Assets.Abbreviation       AS "Asset",
    Targets.TargetDeciPercent AS "TargetDeciPercent"
FROM
    Targets
INNER JOIN
    Assets ON Targets.AssetID == Assets.ID
;


INSERT INTO AssetGroups (ID, Name) VALUES (1, "Stocks");
INSERT INTO AssetGroups (ID, Name) VALUES (2, "Bonds");
INSERT INTO AssetGroups (ID, Name) VALUES (3, "Cash");


INSERT INTO TaxGroups (ID, Name) VALUES (1, "Taxable");
INSERT INTO TaxGroups (ID, Name) VALUES (2, "Tax Deferred");
INSERT INTO TaxGroups (ID, Name) VALUES (3, "Roth");


INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (1, 1, "US TSM");
INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (2, 1, "US SC");
INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (3, 1, "ex-US TSM");

INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (4, 2, "US TBM");
INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (5, 2, "ex-US TBM");
INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (6, 2, "LTB");

INSERT INTO Assets (ID, AssetGroupID, Abbreviation) VALUES (7, 3, "Cash");


INSERT INTO Securities (Symbol, AssetID) VALUES ("ITOT",  1);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FZROX", 1);

INSERT INTO Securities (Symbol, AssetID) VALUES ("IJR", 2);
INSERT INTO Securities (Symbol, AssetID) VALUES ("VB",  2);

INSERT INTO Securities (Symbol, AssetID) VALUES ("IXUS",  3);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FZILX", 3);

INSERT INTO Securities (Symbol, AssetID) VALUES ("AGG",   4);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FXNAX", 4);
INSERT INTO Securities (Symbol, AssetID) VALUES ("TFII",  4);

INSERT INTO Securities (Symbol, AssetID) VALUES ("IAGG",  5);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FBIIX", 5);

INSERT INTO Securities (Symbol, AssetID) VALUES ("ILTB", 6);
INSERT INTO Securities (Symbol, AssetID) VALUES ("BLV",  6);

INSERT INTO Securities (Symbol, AssetID) VALUES ("CORE",  7);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FDLXX", 7);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FZFXX", 7);
INSERT INTO Securities (Symbol, AssetID) VALUES ("FDRXX", 7);

-- Taxable
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 1, 2);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 2, 3);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 3, 1);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 4, 4);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 5, 5);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 6, 6);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 1, 7, 7);

-- Tax Deferred
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 1, 4);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 2, 5);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 3, 6);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 4, 3);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 5, 2);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 6, 1);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 2, 7, 7);

-- Roth
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 1, 2);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 2, 1);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 3, 3);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 4, 6);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 5, 5);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 6, 4);
INSERT INTO AssetAffinities (User, TaxGroupID, AssetID, Priority) VALUES ("DEFAULT", 3, 7, 7);

INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 1, 337);
INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 2,  50);
INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 3, 313);
INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 4,  50);
INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 5,  50);
INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 6, 200);
INSERT INTO Targets (User, AssetID, TargetDeciPercent) VALUES ("DEFAULT", 7,   0);

PRAGMA user_version=1;

COMMIT;