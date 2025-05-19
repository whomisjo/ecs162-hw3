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

# GET comments (anyone can read)
@app.route("/api/articles/<path:slug>/comments", methods=["GET"])
def get_comments(slug):
    cursor = comments.find({"article": slug})
    result = []
    for doc in cursor:
        result.append({
            "id":      str(doc["_id"]),
            "author":  doc.get("author", "unknown"),
            "text":    doc.get("text", ""),
            "created": doc.get("created")
        })
    return jsonify(result)

# POST a new comment (must be logged in)
@app.route("/api/articles/<path:slug>/comments", methods=["POST"])
def post_comment(slug):
    user = session.get("user")
    if not user:
        return jsonify({ "error": "Not logged in" }), 401

    data = request.get_json()
    if not data or "text" not in data or not data["text"].strip():
        return jsonify({ "error": "Missing or empty 'text' field" }), 400

    # Build & save the comment
    comment = {
        "article": slug,
        "text":    data["text"].strip(),
        "author":  user["email"],
        "created": datetime.utcnow()
    }
    result = comments.insert_one(comment)

    # Shape the response
    comment["id"]      = str(result.inserted_id)
    comment.pop("_id", None)
    comment["created"] = comment["created"].isoformat()

    return jsonify(comment), 201

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