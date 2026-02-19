from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, current_app
from db_instance import db
import models
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token
from werkzeug.utils import secure_filename
import uuid
import os
import base64
from app import allowed_file
import face_recognition # face_recognitionをインポート
import numpy as np
import cv2 # cv2は画像処理ライブラリであり、face_recognitionと連携して使用することがあります。
from app import allowed_file

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """ステップ1: ユーザー基本情報登録"""
    # API経由でのJSONデータ登録 (既存のロジックを保持)
    if request.is_json:
        # TODO: APIからの登録も多段階にする場合はこのロジックを変更する必要あり
        # 現状は単一リクエストで完結する従来のロジックを保持
        username = request.json.get('username', None)
        user_age = request.json.get('user_age', None)
        email = request.json.get('email', None)
        password = request.json.get('password', None)
        
        # バリデーション
        if not user_age or not username or not email or not password:
            return jsonify({'message': 'Username, email, password, and age are required'}), 400
        try:
            user_age = int(user_age)
            if user_age <= 0:
                return jsonify({'message': 'Age must be a positive integer'}), 400
        except ValueError:
            return jsonify({'message': 'Age must be a number'}), 400
        
        # ユーザー名またはメールアドレスが既に存在するかチェック
        existing_user = models.User.query.filter((models.User.username == username) | (models.User.email == email)).first()
        if existing_user:
            return jsonify({'message': 'Username or email already exists'}), 400

        # 新規ユーザー作成
        user = models.User(username=username, user_age=user_age, email=email, role='user')
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.commit()
            return jsonify({'message': 'User registered successfully'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'Registration failed: {str(e)}'}), 500

    # HTMLフォームからの登録（多段階登録の開始）
    if request.method == 'POST':
        # フォームデータをセッションに保存して次のステップへ
        username = request.form['username']
        user_age = request.form['user_age']
        email = request.form['email']
        password = request.form['password']
        bio = request.form.get('bio', None)
        profile_image_file = request.files.get('profile_image_file')

        # バリデーション
        if not username or not user_age or not email or not password:
            flash('全ての必須項目を入力してください。', 'danger')
            return redirect(url_for('auth.register'))
        try:
            user_age = int(user_age)
            if user_age <= 0:
                flash('年齢は正の整数で入力してください。', 'danger')
                return redirect(url_for('auth.register'))
        except ValueError:
            flash('年齢は数字で入力してください。', 'danger')
            return redirect(url_for('auth.register'))

        existing_user = models.User.query.filter((models.User.username == username) | (models.User.email == email)).first()
        if existing_user:
            flash('ユーザー名またはメールアドレスは既に登録されています。', 'danger')
            return redirect(url_for('auth.register'))
        
        # プロフィール画像のアップロードと保存
        profile_image_path = None
        if profile_image_file and profile_image_file.filename != '':
            if not allowed_file(profile_image_file.filename, current_app.config):
                flash('許可されていない画像ファイル形式です。', 'danger')
                return redirect(url_for('auth.register'))
            
            filename = secure_filename(profile_image_file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            
            try:
                profile_image_file.save(file_path)
                profile_image_path = url_for('static', filename=f'uploads/{unique_filename}')
            except Exception as e:
                flash(f'プロフィール画像の保存に失敗しました: {str(e)}', 'danger')
                return redirect(url_for('auth.register'))

        # フォームデータをセッションに保存して次のステップへ
        session['registration_data'] = {
            'username': username,
            'user_age': user_age,
            'email': email,
            'password_hash': generate_password_hash(password),
            'bio': bio,
            'profile_image': profile_image_path
        }
        
        flash('基本情報の登録が完了しました。次に身分証明書をアップロードしてください。', 'success')
        return redirect(url_for('auth.register_id_card'))

    # GETリクエストの場合、またはPOSTでエラーがあった場合
    return render_template('auth/register.html')


@bp.route('/register/id_card', methods=['GET', 'POST'])
def register_id_card():
    """ステップ2: 身分証明書アップロード"""
    # セッションに登録データがなければ最初の登録ページに戻す
    if 'registration_data' not in session:
        flash('アカウント登録を最初からやり直してください。', 'warning')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        if 'id_card_file' not in request.files or request.files['id_card_file'].filename == '':
            flash('身分証明書のファイルを選択してください。', 'danger')
            return redirect(request.url)
        
        file = request.files['id_card_file']
        if not allowed_file(file.filename, current_app.config):
            flash('許可されていないファイル形式です。', 'danger')
            return redirect(request.url)

        try:
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # セッションに画像パスを保存
            session['registration_data']['id_card_image'] = url_for('static', filename=f'uploads/{unique_filename}')
            flash('身分証明書がアップロードされました。次に顔写真を撮影してください。', 'success')

            return redirect(url_for('auth.register_face_scan'))
        except Exception as e:
            flash(f'アップロードに失敗しました: {str(e)}', 'danger')
            return redirect(request.url)

    return render_template('auth/register_id_card.html')


@bp.route('/register/face_scan', methods=['GET'])
def register_face_scan():
    """ステップ3: 顔写真撮影と認証"""
    if 'registration_data' not in session or 'id_card_image' not in session['registration_data']:
        flash('アカウント登録を最初からやり直してください。', 'warning')
        return redirect(url_for('auth.register'))
    
    return render_template('auth/register_face_scan.html')


@bp.route('/register/verify_face', methods=['POST'])
def register_verify_face():
    """顔写真のアップロードと顔照合のAPIエンドポイント"""
    if 'registration_data' not in session or 'id_card_image' not in session['registration_data']:
        return jsonify({'message': 'セッション情報が無効です。アカウント登録を最初からやり直してください。', 'redirect_url': url_for('auth.register')}), 400

    data = request.get_json()
    face_scan_image_data = data.get('image')
    if not face_scan_image_data:
        return jsonify({'message': '顔画像データがありません。'}), 400

    try:
        # 身分証明書の画像パスを取得
        id_card_image_path = session['registration_data']['id_card_image']
        id_card_image_full_path = os.path.join(current_app.root_path, id_card_image_path.lstrip('/'))
        
        # 顔写真をファイルとして保存
        header, encoded = face_scan_image_data.split(",", 1)
        binary_data = base64.b64decode(encoded)
        unique_filename = str(uuid.uuid4()) + '_face_scan.png'
        face_scan_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        with open(face_scan_file_path, 'wb') as f:
            f.write(binary_data)
        face_scan_image_path = url_for('static', filename=f'uploads/{unique_filename}')

        # --- 顔照合ロジック ---
        is_match = False
        try:
            # 身分証明書の画像を読み込み、顔エンコーディングを生成
            id_card_img_np = face_recognition.load_image_file(id_card_image_full_path)
            id_card_face_encodings = face_recognition.face_encodings(id_card_img_np)

            # 撮影した顔写真を読み込み、顔エンコーディングを生成
            face_scan_img_np = face_recognition.load_image_file(face_scan_file_path)
            face_scan_face_encodings = face_recognition.face_encodings(face_scan_img_np)

            if id_card_face_encodings and face_scan_face_encodings:
                # 2つの顔を比較
                matches = face_recognition.compare_faces([id_card_face_encodings[0]], face_scan_face_encodings[0])
                is_match = matches[0]
            else:
                return jsonify({'message': '顔を検出できませんでした。もう一度お試しください。', 'status': 'failed', 'redirect_url': url_for('auth.register_face_scan')}), 400
        except Exception as e:
            # 認証失敗時の画像ファイル削除
            if os.path.exists(face_scan_file_path):
                os.remove(face_scan_file_path)
            return jsonify({'message': f'顔認証処理中にエラーが発生しました: {str(e)}', 'status': 'error', 'redirect_url': url_for('auth.register_face_scan')}), 500

        if is_match:
            # 照合成功、データベースにユーザーを登録（Adminの年齢確認待ち）
            registration_data = session.pop('registration_data')
            new_user = models.User(
                username=registration_data['username'],
                user_age=registration_data['user_age'],
                email=registration_data['email'],
                password_hash=registration_data['password_hash'],
                bio=registration_data['bio'],
                profile_image=registration_data['profile_image'],
                id_card_image=registration_data['id_card_image'],
                face_scan_image=face_scan_image_path,
                is_verified=False, # ここはFalseのまま
                verification_status='uploaded_both', # Adminの確認待ち
                role='user'
            )
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({'message': '顔認証が成功しました。次に、Adminが生年月日と年齢を照合します。', 'status': 'success', 'redirect_url': url_for('auth.login')}), 200
        else:
            # 認証失敗、最初からやり直させる
            if os.path.exists(face_scan_file_path):
                os.remove(face_scan_file_path)
            session.pop('registration_data', None)
            return jsonify({'message': '顔認証に失敗しました。もう一度登録し直してください。', 'status': 'failed', 'redirect_url': url_for('auth.register')}), 400
    
    except Exception as e:
        db.session.rollback()
        session.pop('registration_data', None)
        return jsonify({'message': f'登録中にエラーが発生しました: {str(e)}', 'status': 'error', 'redirect_url': url_for('auth.register')}), 500

    return jsonify({'message': '無効なリクエストです。'}), 400


# 既存の login と logout ルートは変更なし
@bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... 既存のロジック ...
    if request.is_json:
        username = request.json.get('username', None)
        password = request.json.get('password', None)
        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400

        user = models.User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify({"message": "Invalid username or password"}), 401
        
        # 認証済みユーザーのみログイン可能とする場合はここで is_verified をチェック
        # if not user.is_verified:
        #     return jsonify({"message": "アカウントはまだ本人確認が完了していません。"}), 401

        access_token = create_access_token(identity=user.username)
        return jsonify(access_token=access_token), 200

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = models.User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # 認証済みユーザーのみログイン可能とする場合はここで is_verified をチェック
            # if not user.is_verified:
            #     flash('アカウントはまだ本人確認が完了していません。', 'warning')
            #     return render_template('auth/login.html')

            session['user_id'] = user.id
            session['username'] = user.username
            flash('ログインしました！', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('ユーザー名またはパスワードが間違っています。', 'danger')
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('ログアウトしました。', 'info')
    return redirect(url_for('auth.login'))