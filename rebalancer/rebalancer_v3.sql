BEGIN TRANSACTION;

CREATE TABLE Quotes
(
    Symbol     VARCHAR(8) NOT NULL,
    QuoteTime  TEXT       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    QuoteCents INTEGER    NOT NULL,

    CHECK(LENGTH(Symbol) > 0),
    CHECK(LENGTH(QuoteTime) > 0),

    FOREIGN KEY("Symbol") REFERENCES Securities("Symbol") ON DELETE CASCADE,

    CONSTRAINT SymbolUniqueByTime PRIMARY KEY (Symbol, QuoteTime)
) WITHOUT ROWID;


PRAGMA user_version=3;

COMMIT;
