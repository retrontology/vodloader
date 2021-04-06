from http.server import BaseHTTPRequestHandler
import requests
import json
import logging

class proxy_request_handler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.0'

    def __init__(self, target_port, *args, **kwargs):
        self.logger = logging.getLogger('vodloader.ssl')
        self.target_port = target_port
        super(proxy_request_handler, self).__init__(*args, **kwargs)


    def do_HEAD(self):
        self.forward("HEAD")


    def do_GET(self, body=True):
        self.forward("GET")


    def do_POST(self, body=True):
        self.forward("POST")
    

    def forward(self, req_type):
        url = 'http://{}{}'.format('127.0.0.1:' + str(self.target_port), self.path)
        req_header = self.headers
        if req_type == "POST":
            req_body = self.rfile.read(int(self.headers.get('Content-Length')))
            resp = requests.post(url, headers=req_header, json=json.loads(req_body.decode()), verify=False)
        elif req_type == "GET":
            resp = requests.get(url, headers=req_header, verify=False)
        elif req_type == "HEAD":
            resp = requests.head(url, headers=req_header, verify=False)
        self.send_response(resp.status_code)
        for key in resp.headers.keys():
            if not key in ['Date', 'Server']:
                self.send_header(key, resp.headers[key])
        self.end_headers()
        self.wfile.write(resp.content)

    
    def log_message(self, format, *args):
        self.logger.debug("%s - - %s" %
                         (self.address_string(),
                          format%args))


    def log_error(self, format, *args):
        self.logger.error("%s - - %s" %
                         (self.address_string(),
                          format%args))