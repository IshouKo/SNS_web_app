import os

class Config:
    # Docker Composeで定義するPostgreSQLサービス名と、ユーザー、パスワード、DB名を指定
    # Docker Composeのservice名がdbなので、ホスト名をdbにする
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'postgresql://user:password@db:5432/sns_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False # シグナル追跡を無効化 (非推奨機能のため)

    # セッション管理などに使用する秘密鍵
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_super_secret_key_here'
    
    # JWTの設定
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'super-secret-jwt-key'

    # デバッグモードの設定
    DEBUG = True