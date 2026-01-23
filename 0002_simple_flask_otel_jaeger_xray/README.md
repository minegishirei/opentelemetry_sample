


## セットアップ

このプロジェクトは OpenTelemetry を使用して Flask アプリケーションのトレースを収集し、Jaeger で可視化します。

### 前提条件
- Docker
- Docker Compose

### 起動方法

```bash
docker-compose up --build
```

### サービス

起動後、以下のサービスにアクセスできます:

- **Flask API**: http://localhost:5000
  - `GET /` - "Hello from Flask!" を返す
  - `GET /health` - ヘルスチェック

- **Jaeger UI**: http://localhost:16686
  - OpenTelemetry のトレースを可視化

### テスト

Flask のエンドポイントにリクエストを送信:

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
```

Jaeger UI で Flask からのトレースが表示されることを確認してください。

### ログの確認

```bash
docker-compose logs flask-app
```



