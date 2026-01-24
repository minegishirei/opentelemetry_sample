

## これは何?

OpenTelemetryのサンプルプロジェクトを集めたソースコード群です。




## メモ

ここまでの調査で以下の3層に分けれることがわかりました。

- インステュルメンテーション層
- コレクター層
- 可視化層

厳密に話すと違うのかもしれないが、ツール群はこれだと思っている。



## マネージドな インステュルメンテーション層 かつ collector兼 : ADOT(AWS Distro for OpenTelemetry)

- **ADOT** ADOT(AWS Distro for OpenTelemetry) : AWS が公式で提供（マネージドディストリビューション）
    - Lambda Layer
    - ECS Sidecar
    - 




