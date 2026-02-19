from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from db_instance import db
from models import User, Tweet, Follow
from sqlalchemy import or_
from werkzeug.utils import secure_filename
import uuid
from app import allowed_file # app.pyからヘルパー関数をインポート
import os

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    logged_in_user = User.query.get(session['user_id'])
    if not logged_in_user:
        session.pop('user_id', None)
        session.pop('username', None)
        flash('ユーザーが見つかりません。再ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))

    # フォローしているユーザーのツイートと、自分のツイートを取得
    # サブクエリでフォローしているユーザーIDのリストを取得
    followed_users_ids = [f.followed_id for f in logged_in_user.following]
    
    # 自分のIDもツイート表示対象に含める
    display_user_ids = followed_users_ids + [logged_in_user.id]

    # 該当ユーザーのツイートをタイムスタンプ降順で取得
    tweets = Tweet.query.filter(Tweet.user_id.in_(display_user_ids)).order_by(Tweet.timestamp.desc()).all()

    return render_template('index.html', user=logged_in_user, tweets=tweets)


@bp.route('/post_tweet', methods=['POST'])
def post_tweet():
    if 'user_id' not in session:
        flash('ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))

    body = request.form['body']
    if not body:
        flash('ツイート内容を入力してください。', 'danger')
        return redirect(url_for('main.index'))

    if len(body) > 280:
        flash('ツイートは280文字以内で入力してください。', 'danger')
        return redirect(url_for('main.index'))

    tweet = Tweet(body=body, user_id=session['user_id'])
    db.session.add(tweet)
    db.session.commit()
    flash('ツイートが投稿されました！', 'success')
    return redirect(url_for('main.index'))


@bp.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    target_user = User.query.filter_by(username=username).first_or_404()
    tweets = target_user.tweets.order_by(Tweet.timestamp.desc()).all()

    # ログイン中のユーザーが自分のプロフィールを見ているか
    is_current_user_profile = ('user_id' in session and session['user_id'] == target_user.id)


    is_following = False
    if 'user_id' in session and session['user_id'] != target_user.id:
        logged_in_user = User.query.get(session['user_id'])
        if logged_in_user:
            is_following = db.session.query(Follow).filter_by(
                follower_id=logged_in_user.id,
                followed_id=target_user.id
            ).first() is not None

    # プロフィール更新フォームのPOST処理
    if request.method == 'POST' and is_current_user_profile: # 自分のプロフィールかつPOSTリクエストの場合
        bio = request.form.get('bio', None)
        # ファイルアップロード処理
        profile_image_path = target_user.profile_image # デフォルトは現在の画像パス

        if 'profile_image_file' in request.files: # ファイルが送信されたかチェック
            file = request.files['profile_image_file']
            if file.filename != '': # ファイルが選択されているか
                if allowed_file(file.filename, current_app.config): # 許可された拡張子かチェック
                    filename = secure_filename(file.filename)
                    unique_filename = str(uuid.uuid4()) + '_' + filename
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    try:
                        file.save(file_path)
                        profile_image_path = url_for('static', filename=f'uploads/{unique_filename}')
                    except Exception as e:
                        flash(f'プロフィール画像の保存に失敗しました: {str(e)}', 'danger')
                        return redirect(url_for('main.profile', username=username))
                else:
                    flash('許可されていない画像ファイル形式です。', 'danger')
                    return redirect(url_for('main.profile', username=username))
            else:
                # ファイルが選択されていないが、input type="file"があるため、既存の値を保持する場合はここを調整
                # 今回は空文字列が送られてきたらNoneにする（つまり画像削除）か、既存保持のロジックを組む
                # 現状はファイルが送られなかったら既存のパスを保持
                pass # file.filename == '' の場合は、profile_image_path は変更しない（現在のまま）

        # 'profile_image_remove' チェックボックスがオンの場合、画像を削除
        if request.form.get('profile_image_remove') == 'on':
            profile_image_path = None # DBからパスを削除
        
        target_user.bio = bio # データベースのbioを更新
        target_user.profile_image = profile_image_path # データベースのprofile_imageを更新

        try:
            db.session.commit()
            flash('プロフィールが更新されました！', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'プロフィールの更新に失敗しました: {str(e)}', 'danger')
        
        return redirect(url_for('main.profile', username=username)) # 更新後、プロフィールページにリダイレクト

    # GETリクエストの場合、またはPOSTでエラーがあった場合は表示
    return render_template(
        'profile.html',
        target_user=target_user,
        tweets=tweets,
        is_following=is_following,
        is_current_user_profile=is_current_user_profile # テンプレートにフラグを渡す
    )

    return render_template('profile.html', target_user=target_user, tweets=tweets, is_following=is_following)

@bp.route('/follow/<username>')
def follow(username):
    if 'user_id' not in session:
        flash('ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))

    logged_in_user = User.query.get(session['user_id'])
    target_user = User.query.filter_by(username=username).first_or_404()

    if logged_in_user.id == target_user.id:
        flash('自分自身をフォローすることはできません。', 'danger')
        return redirect(url_for('main.profile', username=username))

    existing_follow = Follow.query.filter_by(
        follower_id=logged_in_user.id,
        followed_id=target_user.id
    ).first()

    if existing_follow:
        flash(f'あなたは既に{username}さんをフォローしています。', 'info')
    else:
        follow_record = Follow(follower_id=logged_in_user.id, followed_id=target_user.id)
        db.session.add(follow_record)
        db.session.commit()
        flash(f'{username}さんをフォローしました！', 'success')

    return redirect(url_for('main.profile', username=username))


@bp.route('/unfollow/<username>')
def unfollow(username):
    if 'user_id' not in session:
        flash('ログインしてください。', 'danger')
        return redirect(url_for('auth.login'))

    logged_in_user = User.query.get(session['user_id'])
    target_user = User.query.filter_by(username=username).first_or_404()

    if logged_in_user.id == target_user.id:
        flash('自分自身をアンフォローすることはできません。', 'danger')
        return redirect(url_for('main.profile', username=username))

    follow_record = Follow.query.filter_by(
        follower_id=logged_in_user.id,
        followed_id=target_user.id
    ).first()

    if follow_record:
        db.session.delete(follow_record)
        db.session.commit()
        flash(f'{username}さんのフォローを解除しました。', 'info')
    else:
        flash(f'あなたは{username}さんをフォローしていません。', 'info')

    return redirect(url_for('main.profile', username=username))