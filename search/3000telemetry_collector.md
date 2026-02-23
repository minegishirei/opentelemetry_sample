OpenTelemetry Collectorの概要/メリット/サンプルコード






参考 : https://opentelemetry.io/ja/docs/collector/


## Collectorを使うべきか?

### Collectorのメリット

アプリケーションから直接バックエンドへデータを送ることは、実は可能です。
それにもかかわらずCollectorを経由するメリットがあるのかどうかですが、実は以下の利点があります。

- コードに直接書かずに済む
- 1つのデータを複数のバックエンド（例：PrometheusとCloudWatchの両方）へ同時に転送できる
- 送信前にデータのフィルタリング、集約、などの処理を一括で行えます。


### Collectorを使う場合

アプリはローカル（またはサイドカー）で動くCollectorにデータを投げ、その後の宛先管理はCollectorの設定ファイル（YAML）に任せます。

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# 1. リソース情報（アプリ名など）を定義
resource = Resource.create({"service.name": "python-app-via-collector"})

# 2. Collectorのレシーバー（デフォルトはlocalhost:4317）を指定
# アプリ側は「どこに送るか」だけ知っていればOK
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)

# 3. トレーサーの設定
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("parent-span"):
    print("Collector経由で送信中...")
```


### Collectorを使わない場合(ダイレクトエクスポート)

以下サンプルコード(動作確認は未実施です。)

```python
import time
import logging

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource

# --- [1. トレース設定] ---
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator

# --- [2. メトリクス設定] ---
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# --- [3. ログ設定] ---
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

# 共通リソース設定 (横串で見るためのID)
resource = Resource.create({
    "service.name": "full-stack-python-app",
    "deployment.environment": "production",
    "cloud.provider": "aws",
})

# --- 初期化処理 ---

# トレース: X-Ray互換ID生成器をセット
tracer_provider = TracerProvider(resource=resource, id_generator=AwsXRayIdGenerator())
trace_exporter = OTLPSpanExporter(endpoint="http://your-direct-endpoint:4317", insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
trace.set_tracer_provider(tracer_provider)

# メトリクス: 60秒間隔で送信
metric_exporter = OTLPMetricExporter(endpoint="http://your-direct-endpoint:4317", insecure=True)
reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)

# ログ: SDKのLoggerProviderを設定
logger_provider = LoggerProvider(resource=resource)
log_exporter = OTLPLogExporter(endpoint="http://your-direct-endpoint:4317", insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
set_logger_provider(logger_provider)

# Pythonの標準loggingをOpenTelemetryにブリッジ
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logger = logging.getLogger("my-app-logger")
logger.addHandler(handler)

# --- 実行コード ---

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
counter = meter.create_counter("hits", unit="1")

with tracer.start_as_current_span("main-operation") as span:
    # 1. トレースにイベントを記録
    span.set_attribute("user.id", "123")
    
    # 2. メトリクスをカウントアップ
    counter.add(1, {"page": "home"})
    
    # 3. ログを出力 (自動的にスパンIDが紐付き、OTLPで送信される)
    logger.info("処理を実行しました。")
    
    print("全シグナルをダイレクト送信中...")

# 送信完了を待機
tracer_provider.shutdown()
meter_provider.shutdown()
logger_provider.shutdown()
```



## OpenTelemetry Collectorの概要図

以下はOpenTelemtryのCollectorの役割を表した図です。
Collectorは中継地点として、Receivers/Processors/Exporters の3つのコンポーネントを経由し別システムへテレメトリデータを送信します。

<img src="https://opentelemetry.io/ja/docs/collector/img/otel-collector.svg" />

引用 : https://opentelemetry.io/ja/docs/collector/

### バラバラなデータを受け取る（Receivers）

古い形式や新しい形式のさまざまな種類のデータ（ログ、メトリクス、トレース）を理解し、コレクタ内部で扱える共通の形式に翻訳して取り込みます。
これにより、特定のベンダーに縛られずに済みます。

### データを加工する（Processors）

取り込んだデータを加工します。

- フィルタリング： 不要なデータを除去してコストを抑える。
- 集計： 細かいデータをまとめて見やすくする。
- 加工・付与： 「どのサーバーからのデータか」といった追加情報を書き込む。

### 好きな場所に送り出す（Exporters）

整理されたデータを分析ツールやデータベースに送り出します。
同時に複数のツール（例：監視ダッシュボードと長期保存用ストレージ）に送ることも可能です。



## サンプルコード

以下の YAML 設定ファイルは、AWS Distro for OpenTelemetry (ADOT) Lambda Layer で使用される OpenTelemetry Collector の標準的な設定です。

参考リンク-Githubより https://github.com/aws-observability/aws-otel-lambda/blob/main/adot/collector/config.yaml

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "localhost:4317"
      http:
        endpoint: "localhost:4318"

exporters:
  debug:
  awsxray:

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [awsxray]
    metrics:
      receivers: [otlp]
      exporters: [debug]
  telemetry:
    metrics:
      address: localhost:8888
```

各セクションの解説を以下にまとめます。


### 1. Receivers (受信設定)

ReceiversはCollectorがアプリケーション（Lambda関数など）から送られてくるデータを受け取る設定を記述します。

- otlp: OpenTelemetry の標準プロトコル (OTLP) を使用します。
    - grpc: `localhost:4317` で待ち受けます。
    - http: `localhost:4318` で待ち受けます。

> **ポイント:localhost:4317はどこへ繋がるのか**
> 
> Lambda 環境では、ADOT コレクターがサイドカー（正確には拡張機能/Extension）として同じ実行環境内で動くため、
> アプリケーションからは `localhost` 宛にデータを投げるだけでよくなります。


### 2. Exporters (送信設定)

ExportersはRecieversで受け取ったデータを外部のサービスへ転送する出口です。

- awsxray: 受信したトレースデータを AWS X-Ray へ送信します。
    - OTLP 形式で届いたトレースデータを、AWS X-Ray が理解できる形式（Segment Documents）に変換して AWS の API へ送信します。
- debug: 受信したデータをコレクターのログ（標準出力）に書き出します。
    - トラブルシューティングの際、このエクスポーターが有効であれば、Lambda の CloudWatch Logs を見ることで「コレクターまでデータが届いているか」を確認できます。


### 3. Service (パイプラインの組み立て)
どの受信機と送信機を組み合わせて、どのようなデータフローを作るかを定義します。

#### pipelines (データフロー)
- traces (トレース)
    - `otlp` で受け取り、`awsxray` へ送ります。
    - これにより、アプリ内の分散トレースが AWS X-Ray で可視化されます。
- metrics (メトリクス)
    - `otlp` で受け取り`debug` へ送ります。
    - デフォルトではメトリクスは X-Ray には送れないため、ここではログに出力する設定(標準出力 (stdout))になっています。
    - lambda内からの標準出力は CloudWatch Logs へ流れます。
    - まとめると `otlp`で受け取り`debug` へ送信し、 `標準出力(stdout)` を経由してCloudWatch Logsへ流れます。

#### telemetry (コレクター自身の監視)
- metrics:
    - このコレクター自体の動作状況（CPU使用率や処理したデータ数など）を `localhost:8888` で公開します。









