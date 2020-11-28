BEGIN TRANSACTION;

ALTER TABLE Accounts ADD COLUMN IsDefault BOOLEAN NOT NULL DEFAULT 0;

CREATE TRIGGER MadeDefaultOnUpdateIfNotExistsAccounts
AFTER
    Update
ON
    Accounts
FOR EACH ROW WHEN
    NEW.IsDefault == 0
BEGIN
    UPDATE
        Accounts
    SET
        IsDefault = 1
    WHERE
        ID         == NEW.ID         AND
        TaxGroupID == NEW.TaxGroupID AND
        NOT EXISTS (SELECT
                        ID
                    FROM
                        Accounts
                    WHERE
                        TaxGroupID == NEW.TaxGroupID AND
                        IsDefault != 0);
END;

CREATE TRIGGER MadeDefaultOnTaxGroupIDUpdateIfNotExistsAccounts
AFTER
    UPDATE
ON
    Accounts
FOR EACH ROW WHEN
    NEW.TaxGroupID != OLD.TaxGroupID
BEGIN
    UPDATE
        Accounts
    SET
        IsDefault = 1
    WHERE
        ID == (SELECT
                   ID
               FROM
                   Accounts
               WHERE
                   TaxGroupID == OLD.TaxGroupID
               LIMIT 1) AND
        NOT EXISTS (SELECT
                        ID
                    FROM
                        Accounts
                    WHERE
                        TaxGroupID == OLD.TaxGroupID AND
                        IsDefault != 0);
END;

CREATE TRIGGER ClearDefaultOnInsertAccounts
AFTER
    INSERT
ON
    Accounts
FOR EACH ROW WHEN
    NEW.IsDefault != 0
BEGIN
    UPDATE
        Accounts
    SET
        IsDefault = 0
    WHERE
        ID         != NEW.ID  AND
        TaxGroupID == NEW.TaxGroupID AND
        IsDefault  != 0;
END;

CREATE TRIGGER ClearDefaultOnUpdateAccounts
AFTER
    UPDATE
ON
    Accounts
FOR EACH ROW WHEN
    NEW.IsDefault != 0
BEGIN
    UPDATE
        Accounts
    SET
        IsDefault = 0
    WHERE
        ID         != NEW.ID  AND
        TaxGroupID == NEW.TaxGroupID AND
        IsDefault  != 0;
END;

DROP VIEW AccountInfoMap;

CREATE VIEW AccountInfoMap
AS
SELECT
    Accounts.ID          AS "AccountID",
    Accounts.Description AS "Description",
    TaxGroups.Name       AS "TaxGroup",
    Accounts.IsDefault   AS "IsDefault"
FROM
    Accounts
INNER JOIN
    TaxGroups ON Accounts.TaxGroupID == TaxGroups.ID
;

PRAGMA user_version=4;

COMMIT;
