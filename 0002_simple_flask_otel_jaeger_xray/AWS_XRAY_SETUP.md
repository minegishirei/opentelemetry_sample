# AWS X-Ray Console セットアップガイド

## 概要

このプロジェクトは OpenTelemetry Collector から直接 AWS X-Ray にトレースを送信できるように設定されています。

## 前提条件

- AWS アカウント
- AWS CLI がインストールされている
- 適切な IAM 権限

## セットアップ手順

### 1. AWS 認証情報の取得

```bash
# AWS コンソールまたは AWS CLI で認証情報を取得
aws configure
```

### 2. 環境変数を設定

`.env` ファイルに AWS 認証情報を入力：

```bash
# .env ファイルを編集
nano .env

# または
cat > .env << EOF
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx...
EOF
```

### 3. Docker Compose で起動

```bash
docker-compose up --build
```

### 4. トレースデータを送信

```bash
# 別のターミナルで
curl http://localhost:3000/
curl http://localhost:3000/health
curl http://localhost:3000/metrics-test
```

### 5. AWS X-Ray Console で確認

```
https://console.aws.amazon.com/xray/home
```

**確認ポイント：**
- Service Map で `flask-app` が表示される
- トレース一覧にリクエストが記録されている
- レイテンシーやエラー情報が表示されている

## アーキテクチャ

```
Flask App
   ↓ (OTLP)
OpenTelemetry Collector
   ├→ Jaeger (ローカル可視化)
   └→ AWS X-Ray (クラウド分析)
```

## トラブルシューティング

### トレースが AWS X-Ray に送信されない

**確認項目：**

1. 認証情報が正しいか
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_SECRET_ACCESS_KEY
   ```

2. IAM 権限が必要：
   - `xray:PutTraceSegments`
   - `xray:PutTelemetryRecords`

3. Collector のログを確認
   ```bash
   docker-compose logs otel-collector | grep -i "xray\|error"
   ```

4. AWS リージョンが正しいか
   ```bash
   echo $AWS_REGION
   ```

### エラーメッセージ

**"Unable to assume IAM role"**
- IAM 権限不足
- 認証情報の有効期限切れ

**"Region not found"**
- `AWS_REGION` 環境変数が設定されていない

## ローカルテスト (local_mode)

ローカルでのみテストしたい場合：

```yaml
# otel-collector-config.yaml
exporters:
  awsxray:
    region: "us-east-1"
    local_mode: true  # ← AWS に送信しない
```

X-Ray Daemon のログで受け取りを確認：

```bash
docker-compose logs xray-daemon
```

## 本番環境への展開

### AWS ECS での実行例

```yaml
# task-definition.json
{
  "containerDefinitions": [
    {
      "name": "otel-collector",
      "image": "otel/opentelemetry-collector-contrib:0.91.0",
      "environment": [
        {
          "name": "AWS_REGION",
          "value": "us-east-1"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/otel-collector",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### AWS Lambda での実行例

```python
# Lambda Layer として OpenTelemetry を追加
import json
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

tracer_provider = TracerProvider()
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)

def lambda_handler(event, context):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("lambda_operation"):
        # Lambda 処理
        pass
    return {
        "statusCode": 200,
        "body": json.dumps("Success")
    }
```

## 参考資料

- [AWS X-Ray](https://docs.aws.amazon.com/xray/)
- [OpenTelemetry AWS X-Ray Exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/awsxrayexporter)
- [AWS IAM ポリシー](https://docs.aws.amazon.com/xray/latest/devguide/security_iam_service-with-iam.html)

## 注意事項

- `.env` ファイルには認証情報が含まれているため、Git にコミットしないこと
- 本番環境では AWS Secrets Manager や Parameter Store を使用すること
- IAM ロールを使用して認証情報の管理を簡素化すること
