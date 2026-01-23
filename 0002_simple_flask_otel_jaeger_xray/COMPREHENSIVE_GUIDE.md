# Flask + OpenTelemetry + Jaeger + AWS X-Ray 統合ガイド

## プロジェクト概要

このプロジェクトは、Flask アプリケーションに OpenTelemetry を統合し、分散トレースとメトリクスを複数のバックエンドに送信するサンプル実装です。

**主な特徴：**
- Flask アプリケーションの自動インストルメンテーション
- OpenTelemetry Collector による一元管理
- Jaeger での分散トレース可視化（ローカル開発用）
- AWS X-Ray との統合（本番環境用）
- カスタムメトリクスの実装例

---

## プロジェクト構成

```
0001_simple_flask_otel_jaeger_xray/
├── flask/
│   ├── app.py                  # Flask アプリケーション本体
│   ├── requirements.txt         # Python 依存パッケージ
│   └── Dockerfile              # Flask コンテナ定義
├── docker-compose.yaml         # 全サービスのコンテナ構成
├── otel-collector-config.yaml  # OpenTelemetry Collector 設定
├── .env                        # AWS 認証情報（.gitignore に含める）
├── .gitignore                  # Git 無視ファイル
├── README.md                   # クイックスタート
├── AWS_XRAY_SETUP.md          # AWS X-Ray セットアップガイド
└── COMPREHENSIVE_GUIDE.md      # このファイル
```

---

## 1. アーキテクチャ

### データフロー図

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Application                         │
│  - HTTP リクエスト処理                                        │
│  - カスタムトレース                                          │
│  - カスタムメトリクス                                        │
└────────────────────┬────────────────────────────────────────┘
                     │ OTLP (gRPC)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│        OpenTelemetry Collector (Contrib)                    │
│  - トレース受信 (gRPC/HTTP)                                 │
│  - バッチプロセッサ                                          │
│  - メモリ制限                                                │
└────┬─────────────────────────────────────────────────────┬──┘
     │                                                       │
     │ OTLP (gRPC)                                          │ X-Ray Protocol
     ▼                                                       ▼
┌──────────────────┐                          ┌────────────────────────┐
│    Jaeger        │                          │   AWS X-Ray            │
│  (ローカル開発)   │                          │  (本番環境)             │
│  UI: :16686      │                          │ Console: AWS Dashboard │
└──────────────────┘                          └────────────────────────┘

メトリクス:
   ▼
┌──────────────────┐
│ Prometheus        │
│ :8888/metrics    │
└──────────────────┘
```

### コンポーネント詳細

| コンポーネント | イメージ | ポート | 役割 |
|---------------|---------|--------|------|
| **Flask App** | python:3.11-slim | 3000 | メイン API サーバー |
| **Jaeger** | jaegertracing/all-in-one:1.52 | 16686 | トレース可視化 UI |
| **OTel Collector** | otel/opentelemetry-collector-contrib:0.91.0 | 4317 | トレース集約 |
| **X-Ray Daemon** | public.ecr.aws/xray/aws-xray-daemon | 2000 | X-Ray トレース受信 |

---

## 2. Flask アプリケーション (`flask/app.py`)

### 実装概要

Flask アプリケーションは OpenTelemetry で完全に計測されています。

### インストルメンテーション

#### トレース設定

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# OTLP エクスポーター設定
otlp_trace_exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)

# トレースプロバイダー設定
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
```

**特徴：**
- Collector の OTLP gRPC エンドポイント に接続
- バッチスパンプロセッサで効率化
- インセキュアモード（開発環境）

#### メトリクス設定

```python
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# OTLP メトリクスエクスポーター
otlp_metric_exporter = OTLPMetricExporter(endpoint="otel-collector:4317", insecure=True)
metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)

# メトリクスプロバイダー設定
metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
```

**特徴：**
- 周期的にメトリクスを Collector に送信
- バッチ処理でオーバーヘッド削減

#### 自動インストルメンテーション

```python
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Flask インストルメンテーション（自動トレース）
FlaskInstrumentor().instrument_app(app)

# HTTP リクエストライブラリインストルメンテーション
RequestsInstrumentor().instrument()
```

**自動的に記録される情報：**
- HTTP メソッド、パス、ステータスコード
- リクエスト処理時間
- エラー情報
- HTTP ヘッダー（ユーザーエージェントなど）

### カスタムメトリクス

```python
meter = metrics.get_meter(__name__)

# カウンター: 総リクエスト数
request_counter = meter.create_counter(
    name="flask_requests_total",
    description="Total number of Flask requests"
)

# ヒストグラム: リクエスト処理時間
request_duration = meter.create_histogram(
    name="flask_request_duration_seconds",
    description="Flask request duration in seconds"
)
```

**使用例：**

```python
@app.route("/")
def hello():
    start_time = time.time()
    request_counter.add(1, {"endpoint": "/"})
    duration = time.time() - start_time
    request_duration.record(duration, {"endpoint": "/"})
    return jsonify({"message": "Hello from Flask with X-Ray!"})
```

### エンドポイント一覧

| メソッド | パス | 説明 | メトリクス |
|---------|------|------|-----------|
| GET | `/` | メインエンドポイント | リクエスト数 + 処理時間 |
| GET | `/health` | ヘルスチェック | リクエスト数 + 処理時間 |
| GET | `/metrics-test` | メトリクステスト (0.1s遅延) | リクエスト数 + 処理時間 |

### 依存パッケージ

```
Flask==3.0.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp==1.21.0
opentelemetry-instrumentation-flask==0.42b0
opentelemetry-instrumentation-requests==0.42b0
opentelemetry-exporter-jaeger==1.21.0
aws-xray-sdk==2.12.1
```

---

## 3. OpenTelemetry Collector 設定

### 役割

Collector は以下の3つの処理を行います：

1. **受信（Receiver）** - Flask からトレース・メトリクスを受信
2. **処理（Processor）** - スパンをバッチ化、メモリ管理
3. **エクスポート（Exporter）** - Jaeger と AWS X-Ray に送信

### 設定ファイル (`otel-collector-config.yaml`)

#### Receivers 設定

```yaml
receivers:
  otlp:
    protocols:
      grpc:  # gRPC プロトコル (ポート 4317)
      http:  # HTTP プロトコル (ポート 4318)
```

**特徴：**
- gRPC と HTTP の両方をサポート
- Flask は gRPC を使用（高速・低オーバーヘッド）

#### Processors 設定

```yaml
processors:
  batch:  # バッチプロセッサ
  memory_limiter:
    check_interval: 1s
    limit_mib: 512  # 最大 512MB メモリ
```

**バッチプロセッサの利点：**
- 複数のスパンをまとめてエクスポート
- ネットワークオーバーヘッド削減
- スループット向上

**メモリリミッターの役割：**
- メモリ使用量が設定値を超えないように監視
- メモリ逼迫時にサンプリングレート低下

#### Exporters 設定

```yaml
exporters:
  otlp:
    endpoint: jaeger:4317
    tls:
      insecure: true  # 開発環境
  awsxray:
    region: "us-east-1"
    # local_mode: false で AWS にトレース送信
```

**OTLP エクスポーター:**
- Jaeger の gRPC エンドポイントに接続
- インセキュアモード（自己署名証明書許可）

**AWS X-Ray エクスポーター:**
- X-Ray Protocol でネイティブ送信
- AWS IAM 認証サポート
- `local_mode: false` で実 AWS に送信

#### Service Pipeline 設定

```yaml
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, memory_limiter]
      exporters: [otlp, awsxray]  # 両方に送信
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
```

**トレースパイプライン:**
- Flask → Collector → (Jaeger + AWS X-Ray)

**メトリクスパイプライン:**
- Flask → Collector → Jaeger (Prometheus 互換)

---

## 4. Docker Compose 構成

### サービス定義

#### Jaeger

```yaml
jaeger:
  image: "jaegertracing/all-in-one:1.52"
  ports:
    - "16686:16686"
  expose:
    - 4317
    - 4318
  environment:
    - COLLECTOR_ZIPKIN_HOST_PORT=:9411
    - COLLECTOR_OTLP_ENABLED=true
```

**機能：**
- Web UI: http://localhost:16686
- OTLP gRPC レシーバー
- Zipkin 互換性

#### OpenTelemetry Collector

```yaml
otel-collector:
  image: otel/opentelemetry-collector-contrib:0.91.0
  command: ["--config=/etc/otel-collector-config.yaml"]
  volumes:
    - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
  ports:
    - 4317:4317
  environment:
    - AWS_REGION=${AWS_REGION:-us-east-1}
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
  depends_on:
    - jaeger
```

**特徴：**
- Contrib バージョン（AWS X-Ray サポート）
- 環境変数で AWS 認証情報を渡す
- Jaeger に依存

#### Flask App

```yaml
flask-app:
  build:
    context: ./flask
  ports:
    - "3000:3000"
  environment:
    - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
  depends_on:
    - otel-collector
```

**機能：**
- API: http://localhost:3000
- Collector に OTLP で接続

#### X-Ray Daemon

```yaml
xray-daemon:
  image: public.ecr.aws/xray/aws-xray-daemon:latest
  ports:
    - "2000:2000/udp"
    - "2000:2000/tcp"
  environment:
    - LOG_LEVEL=info
    - AWS_REGION=us-east-1
    - LOCAL_MODE=true  # ローカルテスト用
```

**役割：**
- トレースデータ受信（UDP/TCP）
- ローカルストレージに保存

---

## 5. 使用方法

### クイックスタート

#### 1. 起動

```bash
# ローカルテスト（Jaeger で確認）
docker-compose up --build
```

#### 2. トレースデータ送信

別のターミナルで：

```bash
# メインエンドポイント
curl http://localhost:3000/

# ヘルスチェック
curl http://localhost:3000/health

# メトリクステスト
curl http://localhost:3000/metrics-test
```

#### 3. Jaeger UI で確認

ブラウザで以下を開く：

```
http://localhost:16686
```

**確認手順：**
1. Service ドロップダウンから `flask-app` を選択
2. Operation は `GET /` など選択
3. "Find Traces" をクリック
4. トレース一覧が表示される
5. トレースをクリックして詳細表示

**トレース詳細情報：**
- スパン階層
- 処理時間（タイムスタンプ）
- タグ（HTTP メソッド、ステータスコード等）
- ログ出力

### AWS X-Ray Console での確認

#### 前提条件

- AWS アカウント
- AWS CLI 設定済み
- 適切な IAM 権限

#### 手順

```bash
# 1. 認証情報を取得
aws configure

# 2. .env ファイルに認証情報を設定
cat > .env << EOF
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx...
EOF

# 3. Docker Compose で起動
docker-compose up --build

# 4. トレースデータを送信
curl http://localhost:3000/

# 5. AWS Console で確認
# https://console.aws.amazon.com/xray/home
```

**AWS Console での確認：**
1. Service Map で Flask → 外部依存関係を表示
2. Traces で詳細を確認
3. Analytics で傾向分析

---

## 6. トレース・メトリクス詳細

### トレース構造

トレースは複数のスパン（Span）から構成されます：

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
├── Span 1: HTTP GET /
│   ├── Duration: 2.3ms
│   ├── Status: OK
│   └── Attributes:
│       ├── http.method = GET
│       ├── http.url = /
│       ├── http.status_code = 200
│       └── span.kind = SERVER
├── Span 2: Flask routing
│   ├── Duration: 1.5ms
│   └── Parent: Span 1
└── Span 3: JSON serialization
    ├── Duration: 0.8ms
    └── Parent: Span 2
```

### メトリクス収集

#### 利用可能なメトリクス

```
# Flask 自動メトリクス
flask_http_requests_total
flask_http_request_duration_seconds
flask_http_request_size_bytes
flask_http_response_size_bytes

# カスタムメトリクス
flask_requests_total{endpoint="/"}
flask_request_duration_seconds{endpoint="/"}
```

#### メトリクス確認方法

```bash
# Prometheus エンドポイント（Collector が提供）
curl http://localhost:8888/metrics

# 特定メトリクスのみ
curl http://localhost:8888/metrics | grep flask_requests_total
```

---

## 7. トラブルシューティング

### トレースが表示されない

| 症状 | 原因 | 解決方法 |
|------|------|--------|
| Flask から Collector に接続できない | Collector が起動していない | `docker-compose logs otel-collector` 確認 |
| Jaeger に表示されない | Collector から Jaeger に送信されていない | Collector ログで OTLP エクスポーター確認 |
| AWS X-Ray に送信されない | 認証情報が無い/無効 | `.env` ファイルと AWS IAM 権限確認 |

### ログ確認コマンド

```bash
# すべてのログ
docker-compose logs

# 特定サービスのログ
docker-compose logs flask-app
docker-compose logs otel-collector
docker-compose logs jaeger
docker-compose logs xray-daemon

# リアルタイム監視
docker-compose logs -f otel-collector
```

### よくあるエラー

#### "connection refused: 127.0.0.1:4317"

```
原因: Collector が起動していない
解決: docker-compose ps で状態確認、ログで起動エラー確認
```

#### "unable to connect to xray-daemon"

```
原因: X-Ray Daemon が停止または接続先が間違っている
解決: docker-compose restart xray-daemon
```

#### "memory limit exceeded"

```
原因: メトリクス/トレースデータが多すぎる
解決: otel-collector-config.yaml で limit_mib を増やす
```

---

## 8. 本番環境への展開

### AWS ECS への展開例

```yaml
# task-definition.json
{
  "family": "flask-otel",
  "containerDefinitions": [
    {
      "name": "flask-app",
      "image": "your-account.dkr.ecr.us-east-1.amazonaws.com/flask-app:latest",
      "portMappings": [{"containerPort": 3000}],
      "environment": [
        {
          "name": "OTEL_EXPORTER_OTLP_ENDPOINT",
          "value": "http://otel-collector:4317"
        }
      ]
    },
    {
      "name": "otel-collector",
      "image": "otel/opentelemetry-collector-contrib:0.91.0",
      "portMappings": [{"containerPort": 4317}],
      "environment": [
        {"name": "AWS_REGION", "value": "us-east-1"}
      ]
    }
  ]
}
```

### AWS Lambda への統合例

```python
import json
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Lambda 環境での初期化
tracer_provider = TracerProvider()
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

def lambda_handler(event, context):
    with tracer.start_as_current_span("lambda_function"):
        # Lambda 処理
        return {
            "statusCode": 200,
            "body": json.dumps("Success")
        }
```

---

## 9. パフォーマンス最適化

### トレースサンプリング

大規模環境ではすべてのトレースを記録するとオーバーヘッドが大きくなります。

```yaml
# otel-collector-config.yaml
processors:
  probabilistic_sampler:
    sampling_percentage: 10  # 10% のみ記録
```

### バッチサイズ調整

```yaml
processors:
  batch:
    send_batch_size: 256      # バッチサイズ
    timeout: 10s              # タイムアウト
    send_batch_max_size: 512  # 最大サイズ
```

### メモリ制限

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 1024           # 1GB に増加
    spike_limit_mib: 256
```

---

## 10. セキュリティ考慮事項

### 本番環境でのセキュア設定

```yaml
exporters:
  otlp:
    endpoint: jaeger:4317
    tls:
      insecure: false         # TLS 有効化
      cert_file: /path/to/cert.pem
      key_file: /path/to/key.pem
  awsxray:
    region: "us-east-1"
    # local_mode: false (AWS に送信)
```

### 認証情報の管理

```bash
# ❌ 避けるべき
export AWS_ACCESS_KEY_ID=AKIA...

# ✅ 推奨: AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id otel/aws-credentials
```

### 機密データのマスキング

```python
# スパンに機密情報を含めない
request_counter.add(1, {"endpoint": "/"})  # ✅ OK
request_counter.add(1, {"api_key": "secret123"})  # ❌ NG
```

---

## 11. 参考資料

### 公式ドキュメント

- [OpenTelemetry 公式](https://opentelemetry.io/)
- [OpenTelemetry Python](https://opentelemetry-python.readthedocs.io/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [Jaeger](https://www.jaegertracing.io/docs/)
- [AWS X-Ray](https://docs.aws.amazon.com/xray/)
- [Flask](https://flask.palletsprojects.com/)

### 関連リソース

- [OpenTelemetry 日本語ガイド](https://speakerdeck.com/ymotongpoo)
- [分散トレーシング入門](https://www.oreilly.co.jp/)
- [AWS X-Ray ベストプラクティス](https://aws.amazon.com/jp/builders/seminar/)

---

## 12. クイックリファレンス

### よく使うコマンド

```bash
# サービス起動
docker-compose up --build

# サービス停止
docker-compose down

# コンテナ再起動
docker-compose restart

# ログ確認
docker-compose logs -f [service-name]

# ネットワーク確認
docker-compose ps

# イメージ再ビルド
docker-compose build --no-cache
```

### アクセスURL

| サービス | URL |
|---------|-----|
| Flask API | http://localhost:3000 |
| Jaeger UI | http://localhost:16686 |
| Prometheus Metrics | http://localhost:8888/metrics |
| AWS X-Ray Console | https://console.aws.amazon.com/xray/home |

### API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/` | メインエンドポイント |
| GET | `/health` | ヘルスチェック |
| GET | `/metrics-test` | メトリクステスト |

---

## まとめ

このプロジェクトは、以下の学習ができます：

1. **OpenTelemetry の基礎** - トレース・メトリクスの自動収集
2. **Collector の運用** - 複数バックエンドへのデータ転送
3. **Jaeger の使用方法** - トレースの可視化と分析
4. **AWS X-Ray 統合** - 本番環境への展開方法
5. **Docker による分散システム** - 複数コンポーネントの管理

開発環境から本番環境まで、実用的なオブザーバビリティスタックの実装例です。

---

**最終更新:** 2026年1月22日  
**バージョン:** 1.0
