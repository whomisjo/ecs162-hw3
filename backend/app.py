from flask_cors import CORS
import os
import requests
from datetime import datetime
from flask import (
    Flask, redirect, session, jsonify, request, abort,
    send_from_directory
)
from authlib.integrations.flask_client import OAuth
from authlib.common.security import generate_token
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
load_dotenv('.env.dev')

# ─── Flask setup ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="dist", static_url_path="/")
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config.update(
  SESSION_COOKIE_DOMAIN="localhost",
  SESSION_COOKIE_SAMESITE="Lax",     # or “None” if you need cross-site / iframe flows
  SESSION_COOKIE_HTTPONLY=True,
)

CORS(app,
     supports_credentials=True,
     origins=["http://localhost:5173"])

# ─── OAuth / OIDC client ───────────────────────────────────────────────────────
oauth = OAuth(app)
nonce = generate_token()
oauth.register(
    name=os.getenv('OIDC_CLIENT_NAME'),
    client_id=os.getenv('OIDC_CLIENT_ID'),
    client_secret=os.getenv('OIDC_CLIENT_SECRET'),

    #server_metadata_url='http://dex:5556/.well-known/openid-configuration',
    #authorization_endpoint="http://localhost:5556/auth",
    authorize_url="http://localhost:5556/auth",
    token_endpoint="http://dex:5556/token",
    jwks_uri="http://dex:5556/keys",
    userinfo_endpoint="http://dex:5556/userinfo",
    device_authorization_endpoint="http://dex:5556/device/code",
    client_kwargs={'scope': 'openid email profile'}
)

# ─── MongoDB setup ──────────────────────────────────────────────────────────────

mongo_url = os.getenv("MONGO_URI", "mongodb://mongo:27017")
client    = MongoClient(mongo_url)
db        = client.mydatabase
comments  = db.comments          

# ─── Authentication endpoints ──────────────────────────────────────────────────

@app.route("/api/auth/login")
def auth_login():
    resp = oauth.flask_app.authorize_redirect(
        redirect_uri=os.getenv("OIDC_REDIRECT_URI")
    )
    # client name must match what you set in OIDC_CLIENT_NAME
    state_key = f"{oauth.flask_app.name}_state"
    app.logger.debug(f"[LOGIN] session keys: {list(session.keys())}")
    app.logger.debug(f"[LOGIN] saved state → {session.get(state_key)} (key = {state_key})")
    return resp

@app.route("/api/auth/callback")
def auth_callback():
    app.logger.debug(f"[CALLBACK] session keys *before* authorize_access_token: {list(session.keys())!r}")
    app.logger.debug(f"[CALLBACK] incoming state          : {request.args.get('state')!r}")
    token = oauth.flask_app.authorize_access_token()
    user_info = oauth.flask_app.parse_id_token(
        token, nonce=session.get("nonce")
    )
    session["user"] = user_info
    return redirect("http://localhost:5173/") 

@app.route("/api/auth/userinfo")
def userinfo():
    user = session.get("user")
    if not user:
        return jsonify({}), 401
    return jsonify(user), 200

@app.route("/api/auth/logout")
def auth_logout():
    session.clear()
    return redirect("http://localhost:5173/")

# ─── Commenting API ────────────────────────────────────────────────────────────

@app.route("/api/articles/<path:slug>/comments", methods=["GET"])
def get_comments(slug):
    cursor = comments.find({"article": slug})
    result = []
    for doc in cursor:
        result.append({
            "id":        str(doc["_id"]),
            "author":    doc.get("author", "unknown"),
            "text":      doc.get("text", ""),
            "created":   doc.get("created")
        })
    return jsonify(result)

@app.route("/api/articles/<path:slug>/comments", methods=["POST"])
def post_comment(slug):
    #Parse & validate
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    #Build the document
    comment = {
        "article": slug,
        "text":    data["text"],
        "author":  data.get("author", "anonymous"),
        "created": datetime.utcnow()
    }

    result = comments.insert_one(comment)
    comment["id"] = str(result.inserted_id)
    comment.pop("_id", None)
    comment["created"] = comment["created"].isoformat()

    return jsonify(comment), 201

# ─── NYT Proxy ─────────────────────────────────────────────────────────────────

@app.route("/api/key")
def get_key():
    return jsonify({"apiKey": os.getenv("NYT_API_KEY")})

@app.route("/api/stories")
def get_stories():
    key = os.getenv("NYT_API_KEY")
    fq = (
        'timesTag.organization:("University of California, Davis")'
        ' OR timesTag.location:(Sacramento)'
    )
    params = {
        "api-key": key,
        "q":        'Davis OR Sacramento OR "UC Davis" OR UCD',
        "fq":       fq,
        "sort":     "newest"
    }
    resp = requests.get(
        "https://api.nytimes.com/svc/search/v2/articlesearch.json",
        params=params
    )
    return jsonify(resp.json())

# ─── Serve SPA in production ───────────────────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    if path.startswith("api/"):
        return abort(404)
    return send_from_directory(app.static_folder, "index.html")

# ─── Start ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)