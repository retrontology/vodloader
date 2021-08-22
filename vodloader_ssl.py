from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from OpenSSL import crypto
from OpenSSL.SSL import FILETYPE_PEM
from acme import challenges
from acme import client
from acme import crypto_util
from acme import messages
from acme import standalone
import josepy
import logging
from contextlib import contextmanager

DIRECTORY_URL = 'https://acme-staging-v02.api.letsencrypt.org/directory'
USER_KEY_SIZE = 2048
CERT_KEY_SIZE = 2048
DOMAIN = 'retrontology.com'
PORT = 80
USER_AGENT = 'vodloader'
EMAIL = 'retrontology@hotmail.com'

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
def challenge_server(http_01_resources:set, port:int):
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
    """ while True:
        tos_reply = input(f'Do you agree to the ToS of Let\'s Encrypt located at {user.directory.meta.terms_of_service} ? (Y/N): ').lower()
        if tos_reply == 'y':
            break
        elif tos_reply == 'n':
            exit('You must agree to the ToS of Let\'s Encrypt in order to generate an SSL certificate for webhooks.') """
    logger.info("Registering")
    regr = user.new_account(messages.NewRegistration.from_data(email=email, terms_of_service_agreed=True))
    return user, regr

def http01_validate(user:client.ClientV2, challenge:challenges.HTTP01, order:messages.OrderResource, port:int):
    response, validation = challenge.response_and_validation(user.net.key)
    response
    resource = standalone.HTTP01RequestHandler.HTTP01Resource(chall=challenge.chall, response=response, validation=validation)
    with challenge_server({resource}, port):
        #input('Press Enter to advance...')
        user.answer_challenge(challenge, response)
        finalized_order = user.poll_and_finalize(order)
    return finalized_order.fullchain_pem

def get_cert(user:client.ClientV2, domain:str, port:int, key_pem:bytes=None):
    logger.info("Generating CSR...")
    key_pem, csr_pem = new_csr_comp(domain, key_pem)
    
    logger.info('Validating http01 challenge...')
    order = user.new_order(csr_pem)
    challenge = select_http01_challenge(order)
    fullchain_pem = http01_validate(user, challenge, order, port)

    return key_pem, fullchain_pem
