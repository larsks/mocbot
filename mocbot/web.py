import hmac
import json
import os
import zmq

from flask import Flask, request, make_response

app = Flask(__name__)

sock_uri = os.environ.get('GH_SOCKET_URI', 'tcp://127.0.0.1:1509')
webhook_secret = os.environ.get('GH_SECRET_TOKEN')
debug = os.environ.get('GH_DEBUG')

ctx = zmq.Context()
sock = ctx.socket(zmq.PUB)
sock.connect(sock_uri)


class RequestValidationError(Exception):
    pass


class GithubEvents:
    def __init__(self, sock_uri, secret=None):
        self.sock_uri = sock_uri
        self.secret = secret
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.connect(sock_uri)

    def validate_request(self, request):
        '''Validate that an request is well formated and authorized.

        Ensure that a request has an X-Github-Event header and a
        JSON content-type.

        If we are expecting requests to be signed, ensure that a signature
        exists and is correct.
        '''

        if 'x-github-event' not in request.headers:
            raise RequestValidationError('request does not appear to be a webhook event')

        if not request.is_json:
            raise RequestValidationError('request is not json')

        if self.secret:
            if 'x-hub-signature-256' not in request.headers:
                raise RequestValidationError('no signature in request')

            sig = hmac.HMAC(key=self.secret.encode(), digestmod='sha256')
            sig.update(request.data)
            have_sig = 'sha256=' + sig.hexdigest()
            want_sig = request.headers['x-hub-signature-256']

            if not hmac.compare_digest(have_sig, want_sig):
                raise RequestValidationError('request failed signature validation')

        return True

    def send_event(self, event_type, event_data):
        event_type = event_type.encode()
        event_data = json.dumps(event_data).encode()

        self.sock.send_multipart([event_type, event_data])


GE = GithubEvents(sock_uri, secret=webhook_secret)


@app.route('/hook', methods=['POST'])
def handle_webhook():
    try:
        GE.validate_request(request)
    except RequestValidationError as err:
        app.logger.error('request failed: %s', err)
        GE.send_event(
            'error',
            {
                'msg': str(err),
                'remote_addr': request.remote_addr,
                'forwarded_for': request.headers.get('x-forwarded-for'),
            }
        )

        return make_response('Invalid request', 400)
    else:
        GE.send_event(
            request.headers['x-github-event'],
            request.json,
        )

        return make_response('OK')
