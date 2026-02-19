# Pythonのベースイメージ
FROM python:3.9-slim-buster

# コンテナ内の作業ディレクトリを設定
WORKDIR /code

# ホストのrequirements.txtをコンテナの/codeにコピー
# COPY requirements.txt .

# 依存関係をインストール (docker-compose.ymlで実行するためここではコメントアウト)
# RUN pip install --no-cache-dir -r requirements.txt

# ポート5000を公開
EXPOSE 5000

# アプリケーション起動コマンド (docker-compose.ymlで上書きされるためここではコメントアウト)
# CMD ["python", "app.py"]