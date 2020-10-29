import hmac
import json
import os
import zmq

from flask import Flask, request, make_response

app = Flask(__name__)

sock_path = os.environ.get('GH_SOCKET_PATH', '/run/github/github.sock')
webhook_secret = os.environ.get('GH_SECRET_TOKEN')

ctx = zmq.Context()
sock = ctx.socket(zmq.PUB)
sock.connect(f'ipc://{sock_path}')


class RequestValidationError(Exception):
    pass


def validate_request(request):
    if 'x-github-event' not in request.headers:
        raise RequestValidationError('request does not appear to be a webhook event')

    if not request.is_json:
        raise RequestValidationError('request is not json')

    if webhook_secret and 'x-hub-signature' not in request.headers:
        raise RequestValidationError('no signature in request')

    sig = hmac.HMAC(key=webhook_secret, digestmod='sha256')
    sig.update(request.data)
    have_sig = sig.hexdigest()
    want_sig = request.headers['x-hub-signature']

    if not hmac.compare_digest(have_sig, want_sig):
        raise RequestValidationError('request failed signature validation')

    return True


@app.route('/hook', methods=['POST'])
def handle_webhook():
    try:
        validate_request(request)
    except RequestValidationError as err:
        sock.send_multipart([
            b'error',
            json.dumps({
                'msg': str(err),
                'remote_addr': request.remote_addr,
                'forwarded_for': request.headers.get('x-forwarded-for'),
            }).encode()
        ])

        return make_response('Invalid request', 400)
    else:
        sock.send_multipart([
            request.headers['x-github-event'].encode(),
            json.dumps(request.json).encode(),
        ])

        return make_response('OK')
