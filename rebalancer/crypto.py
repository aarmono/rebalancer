from hashlib import sha256, sha512
from base64 import b64encode, b64decode
from functools import partial

try:
    from fastpbkdf2 import pbkdf2_hmac
except ImportError:
    from hashlib import pbkdf2_hmac

from .pyaes import AESModeOfOperationCTR
from .utils import get_salt_from_file

def hash_user_token(user_token):
    salt = get_salt_from_file()
    return hash_user_token_with_salt(user_token, salt)

def hash_user_token_with_salt(user_token, salt):
    return b64encode(pbkdf2_hmac('sha256',
                                 user_token.encode('utf-8'),
                                 salt.encode('utf-8'),
                                 100000)).decode('utf-8')

def hash_account_name(user_token, salt, account_name):
    m = sha512()
    m.update(user_token.encode('utf-8'))
    m.update(account_name.encode('utf-8'))
    account_id = m.digest()

    return b64encode(pbkdf2_hmac('sha256',
                                 account_id,
                                 salt.encode('utf-8'),
                                 100000)).decode('utf-8')

def get_description_key(user_token, salt, account_name):
    m = sha512()
    m.update(account_name.encode('utf-8'))
    m.update(user_token.encode('utf-8'))
    account_id = m.digest()

    key =  pbkdf2_hmac('sha256',
                       account_id,
                       salt.encode('utf-8'),
                       100000)

    return key

def encrypt_account_description(key, account_description):
    aes = AESModeOfOperationCTR(key)

    return b64encode(aes.encrypt(account_description.encode('utf-8'))).decode('utf-8')

def decrypt_account_description(key, encrypted_description):
    aes = AESModeOfOperationCTR(key)

    return aes.decrypt(b64decode(encrypted_description.encode('utf-8'))).decode('utf-8')

def parallel_get_account_hashes_and_keys(user_token,
                                         salt,
                                         account_hashes_to_get,
                                         account_keys_to_get):
    from multiprocessing import Pool
    with Pool() as p:
        account_hashes = {}
        account_keys = {}

        hashes = list(p.map(partial(hash_account_name, user_token, salt),
                            account_hashes_to_get))
        keys = list(p.map(partial(get_description_key, user_token, salt),
                          account_keys_to_get))

        for (account, account_hash) in zip(account_hashes_to_get, hashes):
            key = (user_token, account)
            account_hashes[key] = account_hash

        for (account, account_key) in zip(account_keys_to_get, keys):
            key = (user_token, account)
            account_keys[key] = account_key

        return (account_hashes, account_keys)
