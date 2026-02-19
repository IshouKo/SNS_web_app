# era/routes/api_routes.py
from flask import Blueprint, request, jsonify, g # g はリクエスト固有のデータを保存するオブジェクト
from db_instance import db
import models
from flask_jwt_extended import jwt_required, get_jwt_identity, JWTManager # JWTManagerもインポート

# API用のBlueprintを作成
bp = Blueprint('api', __name__, url_prefix='/api')

# JWTManagerのインスタンスは app.py で作成し、ここで参照できるようにする
# ここではjwtオブジェクトを直接使わず、デコレータとヘルパー関数のみ使用

# ロールチェック用デコレータ (オプション: 管理者権限などが必要なAPI用)
def role_required(required_roles):
    def decorator(fn):
        @jwt_required()
        def wrapper(*args, **kwargs):
            username = get_jwt_identity() # トークンからユーザー名取得
            user = models.User.query.filter_by(username=username).first()
            if user and user.role in required_roles:
                g.current_user = user # 現在のユーザー情報をgオブジェクトに保存
                return fn(*args, **kwargs)
            else:
                return jsonify({'message': 'Permission denied'}), 403
        wrapper.__name__ = fn.__name__ # デコレータが関数の名前を変更しないようにする
        return wrapper
    return decorator

# --- コアAPIエンドポイント ---

# 投稿作成API (認証必須)
@bp.route('/tweets', methods=['POST'])
@jwt_required() # JWT認証必須
def create_tweet_api():
    # トークンから認証済みのユーザー名を取得
    username = get_jwt_identity()
    current_user = models.User.query.filter_by(username=username).first()

    if not current_user:
        return jsonify({"message": "User not found (from token)"}), 404

    data = request.get_json() # JSON形式のリクエストボディを取得
    body = data.get('body')

    if not body:
        return jsonify({"message": "Tweet body is required"}), 400
    if len(body) > 280:
        return jsonify({"message": "Tweet body must be 280 characters or less"}), 400

    tweet = models.Tweet(body=body, user_id=current_user.id)
    db.session.add(tweet)
    db.session.commit()

    return jsonify({"message": "Tweet created successfully", "tweet_id": tweet.id}), 201

# 自分のツイート取得API (認証必須)
@bp.route('/my_tweets', methods=['GET'])
@jwt_required() # JWT認証必須
def get_my_tweets_api():
    username = get_jwt_identity()
    current_user = models.User.query.filter_by(username=username).first()

    if not current_user:
        return jsonify({"message": "User not found (from token)"}), 404

    # 自分のツイートを新しい順に取得
    tweets = current_user.tweets.order_by(models.Tweet.timestamp.desc()).all()

    # ツイートのリストをJSON形式で整形して返す
    tweet_list = []
    for tweet in tweets:
        tweet_list.append({
            "id": tweet.id,
            "body": tweet.body,
            "timestamp": tweet.timestamp.isoformat(), # 日時をISO形式の文字列に変換
            "author_username": current_user.username
        })
    return jsonify(tweet_list), 200

# ユーザープロフィール取得API (誰でもアクセス可能)
@bp.route('/users/<username>', methods=['GET'])
def get_user_profile_api(username):
    user = models.User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    # プロフィール情報をJSONで返す
    return jsonify({
        "username": user.username,
        "email": user.email,
        "user_age": user.user_age,
        "created_at": user.created_at.isoformat(),
        "bio": user.bio, # 新しく追加したbioカラム
        "profile_image": user.profile_image, # 新しく追加したprofile_imageカラム
        "role": user.role # 役割
    }), 200


# プロフィール編集API (認証必須: 自分のプロフィールのみ)
@bp.route('/profile/edit', methods=['PUT']) # PUTメソッドで更新
@jwt_required() # JWT認証必須
def edit_profile_api():
    username = get_jwt_identity() # トークンからユーザー名取得
    current_user = models.User.query.filter_by(username=username).first()

    if not current_user:
        return jsonify({"message": "User not found (from token)"}), 404

    data = request.get_json() # JSON形式のリクエストボディを取得

    # bioとprofile_imageの更新（存在する場合のみ）
    if 'bio' in data:
        current_user.bio = data['bio']
    if 'profile_image' in data:
        current_user.profile_image = data['profile_image']
    
    # 必要に応じて、他のプロフィール項目（例: user_age, email）もここで更新可能
    # ただし、username の変更は通常別途ロジックが必要（ユニーク制約など）

    try:
        db.session.commit() # 変更をコミット
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Failed to update profile: {str(e)}"}), 500


# 例: 管理者のみがアクセスできるAPI (role_requiredデコレータの使用例)
# @bp.route('/admin/users', methods=['GET'])
# @role_required(['admin']) # 'admin'ロールを持つユーザーのみアクセス可能
# def get_all_users_admin_api():
#    users = models.User.query.all()
#    user_list = [{"username": u.username, "email": u.email, "role": u.role} for u in users]
#    return jsonify(user_list), 200