





### オブザーバビリティとは?

省略


### オブザーバビリティツールの構成要素

- インステュルメンテーション層 : サーバー本体への計測器のインストール
- コレクター層 : データを集約し、可視化層へ送信する
- 可視化層 : テレメトリーデータを可視化する


### OpenTelemetryとは？

> OpenTelemetry は API、SDK、ツールのコレクションです。 テレメトリーデータ（メトリクス、ログ、トレース）の計装、生成、収集、エクスポートに使用し、ソフトウェアのパフォーマンスや動作の分析に役立てましょう。

SaaS製のオブザーバビリティツールを導入しようとした時に(NewRelic, DataDogなど)課題となるのがベンダーロックです。
特定の製品で用意されているオブザーバビリティツールの導入を行ったあとで、
別の製品に切り替えようと思ってもスムーズにはいきません。(この現象をベンダーロックインとここで呼称します。)

OpenTelemetryはこの課題を解決する、非ベンダーロックインを目指すツールコレクションです。

- before例 : ベンダーロックインなオブザーバビリティツールのインストール(コードはあくまで具体例です)

```python
import SomeoneSaaS

# SomeoneSaaSでベンダーロックされたコード
...
```

- after例1 : opentelemetryによる 非ベンダーロックイン なコード。`otel-collector:4317` サーバーへメトリクス/トレースを送信している。

```python
from opentelemetry import trace, metrics, context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# ===== OpenTelemetry トレース設定 =====
otlp_trace_exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
tracer = trace.get_tracer(__name__)

# ===== OpenTelemetry メトリクス設定 =====
otlp_metric_exporter = OTLPMetricExporter(endpoint="otel-collector:4317", insecure=True)
metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
meter = metrics.get_meter(__name__)
```

特定のベンダーが用意したインステュルメンテーションツールを使用するのではなく、
どのベンダーでも使用できるOpenTelemetryインステュルメンテーションツールを活用することで、
プロダクトローンチ後でも、オブザーバビリティツールの変更が可能になります。


## 最小構成のサンプルプロジェクト

OpenTelemetryの効果を実感するために、コンテナを使用したサンプルプロジェクトを実装してみます。

- プロジェクトツリー

```
|--docker-compose.yaml
|--flask
|  |--app.py
|  |--Dockerfile
|  |--requirements.txt
|--otel-collector-config.yaml
|--README.md
```

### サンプルアプリケーション

サンプルアプリケーションのURLは以下の通り。

- http://localhost:3000 : `{"message": "Hello from Flask!"}` と表示されるだけの画面
- http://localhost:3000/health : `{"status": "ok"}` と表示されるだけの画面


### サンプルJager




### コマンド

別章の「サンプルコード」のファイルをすべて作成した上で、以下のコマンドを実行することでサンプルアプリケーション/サンプルJager画面が確認できます。

```bash
docker-compose up --build
```



### サンプルコード

- `docker-compose.yaml`

```yml
version: "3"
 
services:
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
  # Collector
  otel-collector:
    image: otel/opentelemetry-collector:0.91.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - 4317:4317 # OTLP gRPC receiver
    depends_on:
      - jaeger
  # Flask アプリケーション
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

- `otel-collector-config.yaml`

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:
 
processors:
  batch:
 
exporters:
  otlp:
    endpoint: jaeger:4317
    tls:
      insecure: true
 
extensions:
  health_check:
  pprof:
  zpages:
 
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
```

- `flask/Dockerfile`

```Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
```

- `flask/requirements.txt`

```
Flask==3.0.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp==1.21.0
opentelemetry-instrumentation-flask==0.42b0
opentelemetry-instrumentation-requests==0.42b0
```

- `flask/app.py`

```python
from flask import Flask
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# OpenTelemetry の設定
otlp_exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

# Flask アプリケーション
app = Flask(__name__)

# Flask インストルメンテーション
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

@app.route("/")
def hello():
    return {"message": "Hello from Flask!"}

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
```








