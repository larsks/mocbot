import hmac
import json
import os
import zmq

from flask import Flask, request, make_response

app = Flask(__name__)

sock_uri = os.environ.get('GH_SOCKET_URI', 'ipc:///run/github/github.sock')
webhook_secret = os.environ.get('GH_SECRET_TOKEN')
debug = os.environ.get('GH_DEBUG')

ctx = zmq.Context()
sock = ctx.socket(zmq.PUB)
sock.connect(sock_uri)


class RequestValidationError(Exception):
    pass


def validate_request(request):
    if 'x-github-event' not in request.headers:
        raise RequestValidationError('request does not appear to be a webhook event')

    if not request.is_json:
        raise RequestValidationError('request is not json')

    if webhook_secret:
        if 'x-hub-signature-256' not in request.headers:
            raise RequestValidationError('no signature in request')

        sig = hmac.HMAC(key=webhook_secret.encode(), digestmod='sha256')
        sig.update(request.data)
        have_sig = 'sha256=' + sig.hexdigest()
        want_sig = request.headers['x-hub-signature-256']

        if debug:
            with open('run/debug.content', 'wb') as fd:
                fd.write(request.data)

            with open('run/debug.have_sig', 'w') as fd:
                fd.write(have_sig)

            with open('run/debug.want_sig', 'w') as fd:
                fd.write(want_sig)

            with open('run/debug.secret', 'w') as fd:
                fd.write(webhook_secret)

        if not hmac.compare_digest(have_sig, want_sig):
            raise RequestValidationError('request failed signature validation')

    return True


@app.route('/hook', methods=['POST'])
def handle_webhook():
    try:
        validate_request(request)
    except RequestValidationError as err:
        app.logger.error('request failed: %s', err)
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
