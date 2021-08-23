import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from OpenSSL import crypto
from acme import challenges
from acme import client
from acme import crypto_util
from acme import messages
from acme import standalone
import josepy
import logging
from contextlib import contextmanager
import pickle
from datetime import datetime
import time
from threading import Thread

DIRECTORY_URL = 'https://acme-staging-v02.api.letsencrypt.org/directory'
USER_KEY_SIZE = 2048
CERT_KEY_SIZE = 2048
PORT = 80
USER_AGENT = 'vodloader'
SSL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssl')
USER_FILENAME = 'letsencrypt.user'
FULLCHAIN_FILENAME = 'fullchain.pem'
PRIVKEY_FILENAME = 'privkey.pem'

logger = logging.getLogger('vodloader.ssl')

        

def new_csr_comp(domain_name:str, key_pem:bytes=None, cert_key_size:int=CERT_KEY_SIZE):
    if key_pem is None:
        # Create private key.
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, cert_key_size)
        key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
    csr_pem = crypto_util.make_csr(key_pem, [domain_name])
    return key_pem, csr_pem

@contextmanager
def challenge_server(http_01_resources:set, port:int=PORT):
    try:
        servers = standalone.HTTP01DualNetworkedServers(('', port), http_01_resources)
        servers.serve_forever()
        yield servers
    finally:
        # Shutdown client web server and unbind from PORT
        servers.shutdown_and_server_close()

def select_http01_challenge(order):
    authz_list = order.authorizations
    for authz in authz_list:
        for i in authz.body.challenges:
            if isinstance(i.chall, challenges.HTTP01):
                return i
    raise Exception('HTTP-01 challenge was not offered by the CA server.')

def get_new_user(email:str, user_key_size:int = USER_KEY_SIZE, directory_url:str = DIRECTORY_URL):
    logger.info("Generating user key")
    user_key = josepy.JWKRSA(
        key=rsa.generate_private_key(
            public_exponent=65537,
            key_size=user_key_size,
            backend=default_backend()
        )
    )
    logger.info("Connecting to Let's Encrypt on {}".format(directory_url))
    net = client.ClientNetwork(user_key, user_agent=USER_AGENT)
    directory = messages.Directory.from_json(net.get(DIRECTORY_URL).json())
    user = client.ClientV2(directory=directory, net=net)
    while True:
        tos_reply = input(f'Do you agree to the ToS of Let\'s Encrypt located at {user.directory.meta.terms_of_service} ? (Y/N): ').lower()
        if tos_reply == 'y':
            break
        elif tos_reply == 'n':
            exit('You must agree to the ToS of Let\'s Encrypt in order to generate an SSL certificate for webhooks.')
    logger.info("Registering")
    regr = user.new_account(messages.NewRegistration.from_data(email=email, terms_of_service_agreed=True))
    return user, regr

def http01_validate(user:client.ClientV2, challenge:challenges.HTTP01, order:messages.OrderResource, port:int=PORT):
    response, validation = challenge.response_and_validation(user.net.key)
    response
    resource = standalone.HTTP01RequestHandler.HTTP01Resource(chall=challenge.chall, response=response, validation=validation)
    with challenge_server({resource}, port):
        #input('Press Enter to advance...')
        user.answer_challenge(challenge, response)
        finalized_order = user.poll_and_finalize(order)
    return finalized_order.fullchain_pem.encode('UTF-8')

def get_certs(user:client.ClientV2, domain:str, port:int=PORT, key_pem:bytes=None):
    logger.info("Generating CSR...")
    key_pem, csr_pem = new_csr_comp(domain, key_pem)
    
    logger.info('Validating http01 challenge...')
    order = user.new_order(csr_pem)
    challenge = select_http01_challenge(order)
    fullchain_pem = http01_validate(user, challenge, order, port)

    return key_pem, fullchain_pem

def user_save(user:client.ClientV2, regr:messages.RegistrationResource, path:str=os.path.join(SSL_DIR, USER_FILENAME)):
    out = (user.net.key.to_json(), regr.to_json())
    with open(path, 'wb') as f:
        pickle.dump(out, f)

def user_load(path:str=os.path.join(SSL_DIR, USER_FILENAME)):
    if os.path.isfile(path):
        with open(path, 'rb') as f:
            key, regr = pickle.load(f)
        regr = messages.RegistrationResource.from_json(regr)
        key = josepy.JWKRSA.from_json(key)
        net = client.ClientNetwork(key, user_agent=USER_AGENT, account=regr)
        directory = messages.Directory.from_json(net.get(DIRECTORY_URL).json())
        user = client.ClientV2(directory=directory, net=net)
        return user, regr
    else:
        raise Exception(f'{path} does not exist!')

def cert_expiration_datetime(fullchain:bytes):
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, fullchain)
    return datetime.strptime(cert.get_notAfter().decode('UTF-8'),'%Y%m%d%H%M%SZ')


class cert_manager():

    def __init__(self, email:str, domain:str):
        self.email = email
        self.domain = domain
        self.privkey_path = os.path.join(SSL_DIR, PRIVKEY_FILENAME)
        self.fullchain_path = os.path.join(SSL_DIR, FULLCHAIN_FILENAME)
        self.user_path = os.path.join(SSL_DIR, USER_FILENAME)
        self.setup_cert()
    
    def setup_cert(self):
        if not os.path.isdir(SSL_DIR):
            os.mkdir(SSL_DIR)
        if os.path.isfile(self.user_path):
            user, regr = user_load()
        else:
            user, regr = get_new_user(self.email)
            user_save(user, regr)
        if os.path.isfile(self.privkey_path):
            privkey = self.read_privkey()
            write_privkey = False
        else:
            privkey = None
            write_privkey = True
        if os.path.isfile(self.fullchain_path):
            fullchain = self.read_fullchain()
            if(cert_expiration_datetime(fullchain).timestamp() - 86400 < time.time()):
                need_cert = True
            else:
                need_cert = False
        else:
            need_cert = True
        if need_cert:
            privkey, fullchain = get_certs(user, self.domain, key_pem=privkey)
            if write_privkey:
                self.write_privkey(privkey)
            self.write_fullchain(fullchain)

    def renew_loop(self, callback=None):
        while True:
            expiration = cert_expiration_datetime(self.read_fullchain()).timestamp() - 86400
            time.sleep(expiration - time.time())
            user, regr = user_load()
            privkey, fullchain = get_certs(user, self.domain, key_pem=self.read_privkey())
            self.write_fullchain(fullchain)
            if callback:
                Thread(target=callback).start()
    
    def start(self, callback=None):
        self.renew_thread = Thread(target=self.renew_loop, args=(callback,))
        self.renew_thread.start()

    def read_fullchain(self):
        return open(self.fullchain_path, 'rb').read()
    
    def read_privkey(self):
        return open(self.privkey_path, 'rb').read()
    
    def write_fullchain(self, fullchain:bytes):
        open(self.fullchain_path, 'wb').write(fullchain)
    
    def write_privkey(self, privkey:bytes):
        open(self.privkey_path, 'wb').write(privkey)