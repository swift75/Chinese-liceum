from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

database = SQLAlchemy()


class User(UserMixin, database.Model):

    id = database.Column(database.Integer, primary_key=True)

    username = database.Column(
        database.String(50),
        unique=True,
        nullable=False
    )

    password_hash = database.Column(
        database.String(255),
        nullable=False
    )

    created_at = database.Column(
        database.DateTime,
        default=datetime.utcnow
    )

    is_active = database.Column(
        database.Boolean,
        default=True
    )

    def __repr__(self):
        return f"<User {self.username}>"


class ChineseWord(database.Model):

    id = database.Column(database.Integer, primary_key=True)

    chinese_text = database.Column(
        database.String(100),
        nullable=False
    )

    pinyin = database.Column(
        database.String(100)
    )

    translation = database.Column(
        database.String(100),
        nullable=False
    )

    example_sentence = database.Column(
        database.Text
    )

    example_translation = database.Column(
        database.Text
    )

    difficulty = database.Column(
        database.Integer,
        default=1
    )

    category = database.Column(
        database.String(50)
    )

    def __repr__(self):
        return f"<Word {self.chinese_text}>"