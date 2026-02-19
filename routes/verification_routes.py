# routes/verification_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from db_instance import db
from models import User
from werkzeug.utils import secure_filename
import uuid
import os
import base64
from app import allowed_file
import face_recognition # face_recognitionをインポート
import numpy as np
import cv2 # cv2をインポート

bp = Blueprint('verification', __name__, url_prefix='/verification')

# 1. 本人確認開始ページ
@bp.route('/')
def verification_start():
    if 'user_id' not in session:
        flash('ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    # すでに本人確認済みであれば、プロフィールページなどにリダイレクト
    if user.is_verified:
        flash('お客様はすでに本人確認済みです。', 'info')
        return redirect(url_for('main.profile', username=user.username))

    return render_template('verification/start.html', user=user)

# 2. 身分証明書アップロード
@bp.route('/upload_id_card', methods=['GET', 'POST'])
def upload_id_card():
    if 'user_id' not in session:
        flash('ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if user.is_verified: # すでに認証済み
        flash('お客様はすでに本人確認済みです。', 'info')
        return redirect(url_for('main.profile', username=user.username))
    
    if request.method == 'POST':
        if 'id_card_file' not in request.files:
            flash('身分証明書のファイルがありません。', 'danger')
            return redirect(request.url)
        
        file = request.files['id_card_file']
        if file.filename == '':
            flash('ファイルが選択されていません。', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename, current_app.config):
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            
            try:
                file.save(file_path)
                # static/uploads/filename.jpg のようにパスを整形
                id_card_image_path = url_for('static', filename=f'uploads/{unique_filename}')
                
                user.id_card_image = id_card_image_path
                user.verification_status = 'uploaded_id' # ステータス更新
                db.session.commit()
                flash('身分証明書がアップロードされました。次に顔写真を撮影してください。', 'success')
                return redirect(url_for('verification.capture_face')) # 次のステップへ
            except Exception as e:
                db.session.rollback()
                flash(f'身分証明書の保存に失敗しました: {str(e)}', 'danger')
                return redirect(request.url)
        else:
            flash('許可されていないファイル形式です。', 'danger')
            return redirect(request.url)

    return render_template('verification/upload_id_card.html', user=user)

# 3. 顔写真撮影
@bp.route('/capture_face', methods=['GET'])
def capture_face():
    if 'user_id' not in session:
        flash('ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if user.is_verified:
        flash('お客様はすでに本人確認済みです。', 'info')
        return redirect(url_for('main.profile', username=user.username))
    
    # 身分証明書がアップロードされているか確認
    if not user.id_card_image or user.verification_status != 'uploaded_id':
        flash('先に身分証明書をアップロードしてください。', 'warning')
        return redirect(url_for('verification.upload_id_card'))

    return render_template('verification/capture_face.html', user=user)

# 4. 顔写真アップロードと認証処理 (APIエンドポイントとして実装)
# フロントエンド（JavaScript）からカメラで撮影した画像データをPOSTする
@bp.route('/verify_face', methods=['POST'])
def verify_face():
    """顔写真アップロードと顔照合のAPIエンドポイント"""
    if 'user_id' not in session:
        return jsonify({'message': '認証が必要です。'}), 401

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'message': 'ユーザーが見つかりません。'}), 404
    
    if user.is_verified:
        return jsonify({'message': 'お客様はすでに本人確認済みです。'}), 200

    if not user.id_card_image:
        return jsonify({'message': '身分証明書がアップロードされていません。'}), 400

    data = request.get_json()
    image_data = data.get('image', None)
    if not image_data:
        return jsonify({'message': '顔画像データがありません。'}), 400
    
    try:
        # 身分証明書の画像パスを取得
        id_card_image_full_path = os.path.join(current_app.root_path, user.id_card_image.lstrip('/'))

        # 顔写真をファイルとして保存
        header, encoded = image_data.split(",", 1)
        binary_data = base64.b64decode(encoded)
        unique_filename = str(uuid.uuid4()) + '_face_scan.png'
        face_scan_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        with open(face_scan_file_path, 'wb') as f:
            f.write(binary_data)
        face_scan_image_path = url_for('static', filename=f'uploads/{unique_filename}')

        # --- 顔照合ロジック ---
        is_match = False
        try:
            id_card_img_np = face_recognition.load_image_file(id_card_image_full_path)
            id_card_face_encodings = face_recognition.face_encodings(id_card_img_np)
            face_scan_img_np = face_recognition.load_image_file(face_scan_file_path)
            face_scan_face_encodings = face_recognition.face_encodings(face_scan_img_np)

            if id_card_face_encodings and face_scan_face_encodings:
                matches = face_recognition.compare_faces([id_card_face_encodings[0]], face_scan_face_encodings[0])
                is_match = matches[0]
            else:
                return jsonify({'message': '顔を検出できませんでした。もう一度お試しください。', 'status': 'failed'}), 400
        except Exception as e:
            if os.path.exists(face_scan_file_path):
                os.remove(face_scan_file_path)
            return jsonify({'message': f'顔認証処理中にエラーが発生しました: {str(e)}', 'status': 'error'}), 500
        
        if is_match:
            # 照合成功、ステータスを更新（Adminの年齢確認待ち）
            user.face_scan_image = face_scan_image_path
            user.verification_status = 'uploaded_both'
            db.session.commit()
            
            message = '顔認証が成功しました。次に、Adminが生年月日と年齢を照合します。'
            status = 'success'
            return jsonify({'message': message, 'status': status, 'redirect_url': url_for('main.profile', username=user.username)}), 200
        else:
            # 照合失敗
            if os.path.exists(face_scan_file_path):
                os.remove(face_scan_file_path)
            message = '顔認証に失敗しました。身分証明書と同一人物か確認してください。'
            status = 'failed'
            return jsonify({'message': message, 'status': status}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'顔認証処理中にエラーが発生しました: {str(e)}', 'status': 'error'}), 500

# その他のAPIエンドポイント (例: 認証ステータスの取得)
@bp.route('/status', methods=['GET'])
def get_verification_status():
    if 'user_id' not in session:
        return jsonify({'message': '認証が必要です。'}), 401
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'message': 'ユーザーが見つかりません。'}), 404
    
    return jsonify({
        'is_verified': user.is_verified,
        'verification_status': user.verification_status,
        'id_card_uploaded': bool(user.id_card_image),
        'face_scan_uploaded': bool(user.face_scan_image)
    }), 200