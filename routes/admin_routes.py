from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort
from db_instance import db
from models import User
import os

bp = Blueprint('admin', __name__, url_prefix='/admin')

def requires_admin_role():
    if 'user_id' not in session:
        flash('ログインが必要です。', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin():
        flash('アクセス権がありません。', 'danger')
        abort(403)

@bp.before_request
def before_request():
    if request.endpoint and 'admin' in request.endpoint:
        requires_admin_role()

@bp.route('/verification')
def verification_queue():
    pending_users = User.query.filter_by(verification_status='uploaded_both').all()
    return render_template('admin/verification.html', pending_users=pending_users)


def delete_images(user):
    """ユーザーの関連画像ファイルをサーバーから削除するヘルパー関数"""
    if user.id_card_image:
        try:
            filepath = os.path.join('static', user.id_card_image.split('uploads/')[1])
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
        user.id_card_image = None
    if user.face_scan_image:
        try:
            filepath = os.path.join('static', user.face_scan_image.split('uploads/')[1])
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
        user.face_scan_image = None

@bp.route('/verification/approve/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.verification_status != 'uploaded_both':
        return jsonify({'message': '無効な操作です。'}), 400

    user.is_verified = True
    user.verification_status = 'approved'
    delete_images(user) # 承認後に画像を削除
    db.session.commit()

    flash(f'{user.username}の本人確認を承認し、関連画像を削除しました。', 'success')
    return jsonify({'message': '承認完了'})


@bp.route('/verification/reject/<int:user_id>', methods=['POST'])
def reject_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.verification_status != 'uploaded_both':
        return jsonify({'message': '無効な操作です。'}), 400

    user.is_verified = False
    user.verification_status = 'rejected'
    delete_images(user) # 拒否後に画像を削除
    db.session.commit()

    flash(f'{user.username}の本人確認を拒否し、関連画像を削除しました。', 'danger')
    return jsonify({'message': '拒否完了'})