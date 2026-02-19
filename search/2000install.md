OpenTelmetry インスト流メンテーション





## 👀 概要

OpenTelemetryには2通りの計測実装方法があります。

- コードベース
- ゼロコード

### 👦 対象読者

### 🔗 参考リンク

- https://opentelemetry.io/ja/docs/concepts/instrumentation/
- https://opentelemetry.io/ja/docs/zero-code/python/

### 📖 関連ページ

- https://pypi.org/project/opentelemetry-instrumentation/


## 内容

OpenTelemetryには2通りの計測実装方法があります。

- コードベース : アプリケーションに直接OpenTelemetryの計測のためのコードを埋め込む方法
- ゼロコード : アプリケーションコードを直接いじらず、起動時のオプション等で計測器を埋め込む方法

特別な事情がない限り、最初はゼロコードを用いて計測器を埋め込む方法が良いと思います。

ゼロコードで素早く形にし、ビジネスモデルが通用するか検証を行い、
ユーザーが増え、複雑な機能が必要になった部分だけをコードベースで再構築させます。

> コードベース ソリューションは、より深い洞察とリッチなテレメトリーをアプリケーション自身から得ることを可能にします。 
>
> 引用 : https://opentelemetry.io/ja/docs/concepts/instrumentation/


### ゼロコード実装のPython例

Pythonの場合、以下のコードでOpenTelemetryライブラリをインストール & 有効化します。

```bash
pip install opentelemetry-distro 
pip install opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install
```

Python起動時のコマンドに `opentelemetry-instrument` をかませることで、計測器の実装は完了します。

```bash
opentelemetry-instrument python myapp.py
```

上記の `opentelemetry-instrument`コマンドは `OTEL_` で始まる環境変数を参照することで 計測器の挙動を設定することができます。


### コードベース

ゼロコード実装ではなく、Pythonコードに直接埋め込む方法もあります。
これはSDKの初期化（プロバイダーの設定）と、どのバックエンド（コンソールやOTLP）に送るかの設定を行う例です。
柔軟な計測が可能になる一方で、メンテナンスの労力も発生するため個人的にはオススメできません。

- ライブラリのインストール

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

- コード例

```python
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# 1. リソースの定義
# サービス名や環境、バージョンなどを設定します
resource = Resource.create(attributes={
    SERVICE_NAME: "payment-api",            # 標準的なサービス名
    "deployment.environment": "production",  # 環境（本番/開発など）
    "service.version": "1.2.0",             # アプリケーションのバージョン
    "host.name": "web-server-01"            # ホスト識別子
})

# 2. トレーサープロバイダーにリソースを紐付け
# これにより、このプロバイダーから作られる全スパンに上記リソースが付与されます
provider = TracerProvider(resource=resource)

# 3. エクスポーターの設定（今回はコンソール出力）
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)

# グローバルなプロバイダーとして登録
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# 4. 実行部分
def process_payment():
    with tracer.start_as_current_span("execute_transaction") as span:
        span.set_attribute("payment.method", "credit_card")
        print("決済処理を実行中...")

if __name__ == "__main__":
    process_payment()
```

コードベース実装自体は個人的にオススメできませんが、 上記のコードで出てきた**リソース** という概念は重要です。

> リソースは、リソース属性としてテレメトリーを生成するエンティティを表します。 
> たとえば、Kubernetes上のコンテナで実行されているテレメトリーを生成するプロセスは、プロセス名、ポッド名、ネームスペース、および場合によってはデプロイメント名を持ちます。 
> これらの4つの属性すべてをリソースに含まれることができます。
> 
> 引用 : https://opentelemetry.io/ja/docs/concepts/resources/

リソースは 「どのサービスの、どのバージョンの、どのコンテナで事象が起きているか」を即座に絞り込むための「テレメトリデータの発生元」と考えています。
上記のコードでは、リソースを特定するアイデンティティとして以下の情報を付与していました。

```python
{
    SERVICE_NAME: "payment-api",            # 標準的なサービス名
    "deployment.environment": "production",  # 環境（本番/開発など）
    "service.version": "1.2.0",             # アプリケーションのバージョン
    "host.name": "web-server-01"            # ホスト識別子
}
```

## デフォルト化する戦略

組織的にOpenTelemetryを運用する場合、デフォルトでOpenTelemetryを有効化する方略があります。
個別のチームにオブザーバビリティを任せると実装の判断軸にバラつきが出るため、**デフォルトでオブザーバビリティを有効化にしつつ、個別事情で無効化する** という戦略です。

- ステップ1 : Dockerfileの ENTRYPOINT (あるいは、ECS タスク定義のcommandオプション)における実行コマンドを以下のように設定します。

```bash
opentelemetry-instrument python app.py
```

- ステップ2 : 個別事情に応じて無効化する。(ECS Environmentsなどでプラットフォーム提供者が無効化する。)

```bash
export OTEL_SDK_DISABLED=true
```















