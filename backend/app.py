import requests
from flask import Flask, redirect, url_for, session, jsonify, request
from authlib.integrations.flask_client import OAuth
from authlib.common.security import generate_token
import os
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)


oauth = OAuth(app)

nonce = generate_token()


oauth.register(
    name=os.getenv('OIDC_CLIENT_NAME'),
    client_id=os.getenv('OIDC_CLIENT_ID'),
    client_secret=os.getenv('OIDC_CLIENT_SECRET'),
    #server_metadata_url='http://dex:5556/.well-known/openid-configuration',
    authorization_endpoint="http://localhost:5556/auth",
    token_endpoint="http://dex:5556/token",
    jwks_uri="http://dex:5556/keys",
    userinfo_endpoint="http://dex:5556/userinfo",
    device_authorization_endpoint="http://dex:5556/device/code",
    client_kwargs={'scope': 'openid email profile'}
)

mongo_url = os.getenv("MONGO_URI", "mongodb://mongo:27017")
client    = MongoClient(mongo_url)
db        = client.mydatabase         
comments  = db.comments             

@app.route("/api/articles/<slug>/comments", methods=["GET"])
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

@app.route("/api/articles/<slug>/comments", methods=["POST"])
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


@app.route('/api/key')
def get_key():
    return jsonify({'apiKey': os.getenv('NYT_API_KEY')})

@app.route('/api/stories')
def get_stories():
    key = os.getenv('NYT_API_KEY')
    fq = (
      'timesTag.organization:("University of California, Davis")' 
      ' OR timesTag.location:(Sacramento)'
    )
    
    params = {
        'api-key': key,
        'q': 'Davis OR Sacramento OR "UC Davis" OR UCD',
        'fq': fq,
        'sort': 'newest',
    }

    resp = requests.get(
        'https://api.nytimes.com/svc/search/v2/articlesearch.json',
        params=params
    )
    return jsonify(resp.json())


@app.route('/')
def home():
    user = session.get('user')
    if user:
        return f"<h2>Logged in as {user['email']}</h2><a href='/logout'>Logout</a>"
    return '<a href="/login">Login with Dex</a>'

@app.route('/login')
def login():
    session['nonce'] = nonce
    redirect_uri = 'http://localhost:8000/authorize'
    return oauth.flask_app.authorize_redirect(redirect_uri, nonce=nonce)

@app.route('/authorize')
def authorize():
    token = oauth.flask_app.authorize_access_token()
    nonce = session.get('nonce')

    user_info = oauth.flask_app.parse_id_token(token, nonce=nonce)  # or use .get('userinfo').json()
    session['user'] = user_info
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
