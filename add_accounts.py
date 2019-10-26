#!/usr/bin/env python3
from csv import DictReader
from collections import defaultdict

from rebalancer import hash_account_name, hash_user_token, encrypt_account_description, get_token_from_file, Database

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

    with Database() as db:
        salt = db.get_user_salt(user_hash = user_hash)
        if salt is None:
            db.add_user(user_hash = user_hash)
            salt = db.get_user_salt(user_hash = user_hash)

        for (account, symbols) in accounts.items():
            print("Found account %s with the following securities" % (account))
            for entry in symbols:
                print("%8s: %s" % entry)

            result = input("Do you want to add this account to the database (Y/N): ")
            if result.upper().strip() == "Y":

                description = input("Enter an account description to identify the account: ")
                tax_status = input("What kind of account is this (1 = Taxable, 2 = Tax Deferred, 3 = Roth): ")

                db.add_account(user_token, account, description, tax_status, salt)

            print("")

        db.commit()


if __name__ == "__main__":
    main()