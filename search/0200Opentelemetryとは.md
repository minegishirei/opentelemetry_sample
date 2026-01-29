OpenTelemetryとは何か?









### OpenTelemetryとは？

> OpenTelemetry は API、SDK、ツールのコレクションです。 テレメトリーデータ（メトリクス、ログ、トレース）の計装、生成、収集、エクスポートに使用し、ソフトウェアのパフォーマンスや動作の分析に役立てましょう。
> 
> 引用 : [OpenTelemetry jp](https://opentelemetry.io/ja/)

SaaS製のオブザーバビリティツールを導入しようとした時に(NewRelic, DataDogなど)課題となるのがベンダーロックです。
特定の製品で用意されているオブザーバビリティツールの導入を行ったあとで、
別の製品に切り替えようと思ってもスムーズにはいきません。(この現象をベンダーロックインとここで呼称します。)

OpenTelemetryはこの課題を解決する、非ベンダーロックインを目指すツールコレクションです。


### Opentelemetryの信頼性

OpenTelemetryはCNCFへ採択され、実験的なツールではなく企業が安心してメインシステムに組み込める信頼を得ています。

> OpenTelemetry was accepted to CNCF on May 7, 2019 and moved to the Incubating maturity level on August 26, 2021.
> (OpenTelemetryは、2019年5月7日にCNCF（クラウドネイティブコンピューティング財団）へ採択され、2021年8月26日には「インキュベーティング（Incubating）」という成熟度レベルに移行しました。)
> 
> 引用 : https://www.cncf.io/projects/opentelemetry/


### OTLP (OpenTelemetry Protocol):

> The OpenTelemetry Protocol (OTLP) specification describes the encoding, transport, and delivery mechanism of telemetry data between telemetry sources, intermediate nodes such as collectors and telemetry backends.
> (OpenTelemetry Protocol（OTLP）仕様は、テレメトリデータをテレメトリの送信元、Collector などの中間ノード、および テレメトリバックエンド の間でやり取りするための、エンコーディング方式・転送方法・配送メカニズムを定義している。)
> 
> OTLP is a general-purpose telemetry data delivery protocol designed in the scope of the OpenTelemetry project.
> (OTLP は、OpenTelemetry プロジェクトの枠組みの中で設計された、汎用的なテレメトリデータ配送プロトコルである。)
> 
> 引用 : https://opentelemetry.io/docs/specs/otlp/

OTLPとは一言でいうと、「テレメトリーデータ（トレース、メトリクス、ログ）を、どういう形式で、どうやって送受信するか」というルールを定義したものです。

基本はgRPCプロトコルをベースにしてます。

OTLPはほぼすべての主要オブザーバビリティベンダーが「標準」として認識し、公式にサポートしています。
以下はOpenTelemetryをネイティブサポートしているベンダーの一覧です。

https://opentelemetry.io/ecosystem/vendors/

これを見ると NewRelic,Datadog,Dynatrace等々の主要なベンダーがNTOPをサポートしているのがわかります。


### OpenTelemetryのツール群

ここでは OpenTelemetryのツール群を以下の二つの要素に分けて説明します。

- OpenTelemetry Instrumentation
- OpenTelemetry Collector

#### OpenTelemetry Instrumentation

アプリケーション側に導入するツール群です。

- SKD

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

- Auto Instrumentation (動作確認未実施です。)

```python
from flask import Flask
import requests

app = Flask(__name__)

@app.route("/")
def hello():
    # 外部へのリクエストも自動でトレースされる
    requests.get("https://www.google.com")
    return "Hello, OpenTelemetry!"

if __name__ == "__main__":
    app.run(port=5000)
```

起動時のスクリプト

```bash
export OTEL_SERVICE_NAME="my-python-app"
export OTEL_TRACES_EXPORTER="console" # テスト用にコンソールへ出力

opentelemetry-instrument python app.py
```



#### OpenTelemetry Collector

メリット : アプリケーションから送られてきたデータを受け取る「中継サーバー」

- アプリケーション側は「とりあえずCollectorに送る」だけで済みます。
- テレメトリデータの送信先を、コードをいじらずに後から変更可能です。「実装後、やはりDatadogにも送りたい。自前のS3にも保存したい」といった変更をCollectorの設定ファイル（YAML）を書き換えるだけで完結できます。










