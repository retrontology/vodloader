from http.server import BaseHTTPRequestHandler
import requests

class proxy_request_handler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.0'

    def do_GET(self, body=True):
        self.forward()


    def do_POST(self, body=True):
        self.forward()


    def forward(self):
        try:
            url = 'https://{}{}'.format('127.0.0.1', self.path)
            req_header = self.parse_headers()
            resp = requests.get(url)
            #self.send_resp_headers(req_header, 11)
            return
        finally:
            self.finish()


    def parse_headers(self):
        req_header = {}
        for line in self.headers.headers:
            line_parts = [o.strip() for o in line.split(':', 1)]
            if len(line_parts) == 2:
                req_header[line_parts[0]] = line_parts[1]
        #req_header = self.strip_auth(req_header)
        return req_header