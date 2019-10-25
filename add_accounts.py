#!/usr/bin/env python3
from csv import DictReader
from collections import defaultdict

from rebalancer import hash_account_name, hash_user_token, get_user_salt, encrypt_account_description, create_db_conn, get_token_from_file

def parse_file(filename):
    accounts = defaultdict(list)

    with open(filename, "r") as f:
        r = DictReader(f)
        for row in r:
            symbol = row["Symbol"]
            description = row["Description"]
            account = row["Account Name/Number"]
            if len(symbol) > 0 and len(account) > 0:
                accounts[account].append((symbol, description))

    return accounts

def main():
    import sys
    from uuid import uuid4

    user_token = get_token_from_file()
    user_hash = hash_user_token(user_token)

    accounts = parse_file(sys.argv[1])

    with create_db_conn() as conn:
        salt = get_user_salt(conn, user_token)
        if salt is None:
            conn.execute('INSERT INTO UserSalts (User) VALUES (?)', (user_hash,))
            salt = get_user_salt(conn, user_token)

        for (account, symbols) in accounts.items():
            print("Found account %s with the following securities" % (account))
            for entry in symbols:
                print("%8s: %s" % entry)

            result = input("Do you want to add this account to the database (Y/N): ")
            if result.upper().strip() == "Y":
                hashed_account = hash_account_name(user_token, account, salt=salt)

                description = input("Enter an account description to identify the account: ")
                tax_status = input("What kind of account is this (1 = Taxable, 2 = Tax Deferred, 3 = Roth): ")

                encrypted_description = None
                if len(description) > 0:
                    encrypted_description = encrypt_account_description(user_token,
                                                                        account,
                                                                        description,
                                                                        salt=salt)

                    conn.execute('INSERT INTO Accounts (ID, Description, TaxGroupID) VALUES (?, ?, ?)',
                                 (hashed_account,
                                  encrypted_description,
                                  tax_status))

            print("")

        conn.commit()


if __name__ == "__main__":
    main()