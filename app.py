from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import click
from db_instance import db
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash
import uuid

# JWTManagerのインスタンスをグローバルに作成
jwt = JWTManager()

def register_cli_commands(app):
    @app.cli.command('init-db')
    def init_db_command():
        """Clear existing data and create new tables."""
        db.create_all()
        click.echo('Initialized the database.')

def allowed_file(filename, app_config):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app_config['ALLOWED_EXTENSIONS']

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, UPLOAD_FOLDER)
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)

    # Blueprintの登録
    from routes import auth_routes, main_routes, api_routes, verification_routes, admin_routes # admin_routesを追加
    from models import User # Userモデルをインポート

    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(main_routes.bp)
    app.register_blueprint(api_routes.bp)
    app.register_blueprint(verification_routes.bp)
    app.register_blueprint(admin_routes.bp) # Admin Blueprintを登録

    register_cli_commands(app)
    
    with app.app_context():
        db.create_all()
        print("Database tables created or already exist.")

        # Adminユーザーが存在しない場合、自動的に作成
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@example.com',
                user_age=99,
                password_hash=generate_password_hash('admin_password'), # 強固なパスワードを設定してください
                role='admin',
                is_verified=True,
                verification_status='approved'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created.")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0')