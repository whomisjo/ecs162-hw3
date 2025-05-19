import unittest
import json
import os
from datetime import datetime
from bson import ObjectId
from flask import Flask, session
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('.env.dev')

from app import app 

class ModeratorDeleteCommentTest(unittest.TestCase):
    def setUp(self):
        #setup test client
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = app.test_client()
        
        mongo_url = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_client = MongoClient(mongo_url)
        self.db = self.mongo_client.test_database
        
        self.db.comments.delete_many({})
        
        self.sample_comment = {
            "article": "test-article",
            "text": "This is a test comment",
            "author": "test@example.com",
            "created": datetime.utcnow()
        }
    
    def tearDown(self):
        self.db.comments.delete_many({})
    
    def test_delete_comment(self):
        """tests if mod can delete"""
        #mocks comment
        comment_id = self.db.comments.insert_one(self.sample_comment).inserted_id
        
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'email': 'moderator@example.com',
                'groups': ['moderator']
            }
        
        response = self.client.delete(
            f'/api/articles/test-article/comments/{str(comment_id)}'
        )
        self.assertEqual(response.status_code, 204)  # 204 = no comment
        
        #check if comment was deleted
        deleted_comment = self.db.comments.find_one({'_id': comment_id})
        self.assertIsNone(deleted_comment)

if __name__ == '__main__':
    unittest.main()