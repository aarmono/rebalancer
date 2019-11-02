from hashlib import sha256, sha512, pbkdf2_hmac
from base64 import b64encode, b64decode

from .pyaes import AESModeOfOperationCTR
from .utils import get_salt_from_file

def hash_user_token(user_token):
    salt = get_salt_from_file()
    return hash_user_token_with_salt(user_token, salt = salt)

def hash_user_token_with_salt(user_token, salt):
    return b64encode(pbkdf2_hmac('sha256',
                                 user_token.encode('utf-8'),
                                 salt.encode('utf-8'),
                                 100000)).decode('utf-8')

def hash_account_name(user_token, account_name, salt):
    m = sha512()
    m.update(user_token.encode('utf-8'))
    m.update(account_name.encode('utf-8'))
    account_id = m.digest()

    return b64encode(pbkdf2_hmac('sha256',
                                 account_id,
                                 salt,
                                 100000)).decode('utf-8')

def get_description_key(user_token, account_name, salt):
    m = sha512()
    m.update(account_name.encode('utf-8'))
    m.update(user_token.encode('utf-8'))
    account_id = m.digest()

    key =  pbkdf2_hmac('sha256',
                       account_id,
                       salt,
                       100000)

    return key

def encrypt_account_description(key, account_description):
    aes = AESModeOfOperationCTR(key)

    return b64encode(aes.encrypt(account_description.encode('utf-8'))).decode('utf-8')

def decrypt_account_description(key, encrypted_description):
    aes = AESModeOfOperationCTR(key)

    return aes.decrypt(b64decode(encrypted_description.encode('utf-8'))).decode('utf-8')
