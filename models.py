from db_instance import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    user_age = db.Column(db.Integer, nullable=False) # 年齢カラムを追加
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(50), default='user') # ユーザーの役割 ('user', 'admin'など)
    bio = db.Column(db.String(500), nullable=True) # 自己紹介
    profile_image = db.Column(db.String(200), nullable=True) # プロフィール画像URL
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- 本人確認機能のために追加するカラム ---
    id_card_image = db.Column(db.String(200), nullable=True)  # 身分証明書の画像パス
    face_scan_image = db.Column(db.String(200), nullable=True) # 顔スキャン（カメラ撮影）の画像パス
    is_verified = db.Column(db.Boolean, default=False)      # 本人確認が完了したかどうかのフラグ
    verification_status = db.Column(db.String(50), default='pending') # 本人確認のステータス (例: 'pending', 'approved', 'rejected')
    # ----------------------------------------

    tweets = db.relationship('Tweet', backref='author', lazy='dynamic')
    following = db.relationship(
        'Follow',
        foreign_keys='Follow.follower_id',
        backref='follower',
        lazy='dynamic'
    )
    followers = db.relationship(
        'Follow',
        foreign_keys='Follow.followed_id',
        backref='followed',
        lazy='dynamic'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self): # 管理者かどうかをチェックするヘルパーメソッド
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username}>'


class Tweet(db.Model):
    __tablename__ = 'tweets'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(280), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f'<Tweet {self.id}: {self.body[:20]}...>'


class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Follower {self.follower_id} follows {self.followed_id}>'