import logging
import os

from flask import Flask, request, Response
from flask.helpers import make_response
from flask_basicauth import BasicAuth
from apscheduler.schedulers.background import BackgroundScheduler
import requests as req
import boto3
import urllib.parse


# Pull config
codeartifact_region = os.environ["CODEARTIFACT_REGION"]
codeartifact_account_id = os.environ["CODEARTIFACT_ACCOUNT_ID"]
codeartifact_domain = os.environ["CODEARTIFACT_DOMAIN"]
codeartifact_repository = os.environ["CODEARTIFACT_REPOSITORY"]
auth_incoming = os.getenv("PROXY_AUTH")

codeartifact_repo_url_443 = bytes(f"https://{codeartifact_domain}-{codeartifact_account_id}.d.codeartifact.{codeartifact_region}.amazonaws.com:443/npm/{codeartifact_repository}/", "utf-8")
codeartifact_repo_url     = bytes(f"https://{codeartifact_domain}-{codeartifact_account_id}.d.codeartifact.{codeartifact_region}.amazonaws.com/npm/{codeartifact_repository}/", "utf-8")

# Logging
logging.basicConfig()
logger = logging.Logger(__name__)

# Make flask
app = Flask(__name__)
if auth_incoming:
    username, password = auth_incoming.split(":")
    app.config['BASIC_AUTH_USERNAME'] = username
    app.config['BASIC_AUTH_PASSWORD'] = password
    app.config['BASIC_AUTH_FORCE'] = True
    basic_auth = BasicAuth(app)


# Token management
client = boto3.client("codeartifact", region_name=codeartifact_region)
AUTH_TOKEN: str


def update_auth_token():
    global AUTH_TOKEN
    AUTH_TOKEN = client.get_authorization_token(
        domain=codeartifact_domain,
        domainOwner=codeartifact_account_id,
        durationSeconds=43200,
    )["authorizationToken"]
    logger.info("Got new token")
    logger.debug("New token: " + AUTH_TOKEN)


def generate_url(path: str) -> str:
    if path.startswith("/"):
        path = path[1:]
    if path.startswith("@") and not ".tgz" in path:
        path = urllib.parse.quote_plus(path)
    return f"https://aws:{AUTH_TOKEN}@{codeartifact_domain}-{codeartifact_account_id}.d.codeartifact.{codeartifact_region}.amazonaws.com:443/npm/{codeartifact_repository}/{path}"

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST"])
def proxy(path):
    logger.info(f"{request.method} {request.path}")

    if request.method == "GET":
        response = req.get(f"{generate_url(path)}")

        if ".tgz" in request.base_url:
            resp = make_response(response.content)
            resp.headers['Content-Type'] = response.headers['Content-Type']
            return resp
        else:
            resp1 = response.content.replace(codeartifact_repo_url_443, b"")
            resp2 = resp1.replace(codeartifact_repo_url, b"")
            resp = make_response(resp2)
            resp.headers['Content-Type'] = response.headers['Content-Type']
            return resp
    elif request.method == "POST":
        response = req.post(f"{generate_url(path)}", json=request.get_json())
        return response.content


if __name__ == "__main__":
    update_auth_token()

    scheduler = BackgroundScheduler()
    job = scheduler.add_job(update_auth_token, "interval", seconds=21600)
    scheduler.start()

    app.run(host='0.0.0.0', port=5000)
