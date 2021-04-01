from http.server import BaseHTTPRequestHandler
import requests

class proxy_request_handler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.0'

    def __init__(self, target_port, *args, **kwargs):
        self.target_port = target_port
        super(proxy_request_handler, self).__init__(*args, **kwargs)


    def do_GET(self, body=True):
        self.forward("GET")


    def do_POST(self, body=True):
        self.forward("POST")
    

    def forward(self, req_type):
        try:
            url = 'http://{}{}'.format('127.0.0.1:' + str(self.target_port), self.path)
            req_header = self.headers
            print(req_header)
            if req_type == "POST":
                req_body = self.rfile.read(int(self.headers.get('Content-Length')))
                print(req_body)
                resp = requests.post(url, headers=req_header, json=req_body, verify=False)
            elif req_type == "GET":
                resp = requests.get(url, headers=req_header, verify=False)
            self.send_response(resp.status_code)
            for key in resp.headers.keys():
                if not key in ['Date', 'Server']:
                    self.send_header(key, resp.headers[key])
            self.end_headers()
            self.wfile.write(resp.content)
        finally:
            pass
            #self.finish()