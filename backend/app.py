from flask_cors import CORS
import os
import secrets
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
  SESSION_COOKIE_SAMESITE="Lax",
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
    #device_authorization_endpoint="http://dex:5556/device/code",
    client_kwargs={"scope": "openid email profile"}
)

# ─── MongoDB setup ──────────────────────────────────────────────────────────────

mongo_url = os.getenv("MONGO_URI", "mongodb://mongo:27017")
client    = MongoClient(mongo_url)
db        = client.mydatabase
comments  = db.comments          

# ─── Authentication endpoints ──────────────────────────────────────────────────

def generate_nonce(length=32):
    return secrets.token_urlsafe(length)

@app.route("/api/auth/login")
def auth_login():
    nonce = generate_nonce()
    session["auth_nonce"] = nonce

    return oauth.flask_app.authorize_redirect(
        redirect_uri=os.getenv("OIDC_REDIRECT_URI"),
        nonce=nonce
    )

@app.route("/api/auth/callback")
def auth_callback():
    token = oauth.flask_app.authorize_access_token()
    user_info = oauth.flask_app.parse_id_token(
        token,
        nonce=session.pop("auth_nonce", None)
    )
    resp = oauth.flask_app.get(
        "http://dex:5556/userinfo",
        token=token
    )
    extra = resp.json()
    user_info.update(extra)

    email = user_info.get("email", "")
    if email == "admin@hw3.com":
        user_info["groups"] = ["moderator", "admin"]
    elif email == "moderator@hw3.com":
        user_info["groups"] = ["moderator"]
    else:
        user_info["groups"] = []  # regular user

    session["user"] = user_info
    return redirect("http://localhost:5173/")

@app.route("/api/auth/userinfo")
def userinfo():
    user = session.get("user")
    if not user:
        return jsonify({}), 401
    return jsonify(user), 200

@app.route("/api/auth/logout", methods=["GET"])
def auth_logout():
    session.clear()
    return redirect("http://localhost:5173/")

# ─── Commenting API ────────────────────────────────────────────────────────────

# GET comments (includes parent)
@app.route("/api/articles/<path:slug>/comments", methods=["GET"])
def get_comments(slug):
    docs = comments.find({"article": slug})
    out = []
    for d in docs:
        out.append({
            "id":      str(d["_id"]),
            "author":  d.get("author", "unknown"),
            "text":    d.get("text", ""),
            "created": d.get("created").isoformat(),
            # Persisted parent or None
            "parent":  d.get("parent")
        })
    return jsonify(out)

# POST new comment or reply
@app.route("/api/articles/<path:slug>/comments", methods=["POST"])
def post_comment(slug):
    user = session.get("user")
    if not user:
        return jsonify({ "error": "Not logged in" }), 401

    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({ "error": "Text is required" }), 400

    # build document
    doc = {
        "article": slug,
        "text":    text,
        "author":  user["email"],
        "created": datetime.utcnow()
    }
    if data.get("parent"):
        doc["parent"] = data["parent"]

    # insert into Mongo:
    res = comments.insert_one(doc)

    # build a clean response dict (no ObjectId anywhere)
    response = {
        "id":      str(res.inserted_id),
        "article": slug,
        "text":    text,
        "author":  user["email"],
        "created": doc["created"].isoformat(),
        "parent":  doc.get("parent")  # None if top-level
    }

    return jsonify(response), 201

# DELETE a comment (only moderators)
@app.route("/api/articles/<path:slug>/comments/<comment_id>", methods=["DELETE"])
def delete_comment(slug, comment_id):
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    # Only moderators can delete
    groups = user.get("groups", [])
    if "moderator" not in groups:
        return jsonify({"error": "Forbidden"}), 403

    result = comments.delete_one({
        "_id":     ObjectId(comment_id),
        "article": slug
    })
    if result.deleted_count == 0:
        return jsonify({"error": "Comment not found"}), 404

    return "", 204

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