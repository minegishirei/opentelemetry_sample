import logging
import time
import json
import random
from datetime import datetime
from flask import Flask, request, jsonify
from opentelemetry import trace, metrics, context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import requests

# ===== ロギング設定 =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# ===== メトリクス定義 =====
# API リクエスト関連
api_request_counter = meter.create_counter(
    name="api_requests_total",
    description="Total number of API requests",
    unit="1"
)

api_request_duration = meter.create_histogram(
    name="api_request_duration_seconds",
    description="API request duration in seconds",
    unit="s"
)

api_error_counter = meter.create_counter(
    name="api_errors_total",
    description="Total number of API errors",
    unit="1"
)

# データ処理関連
data_processing_duration = meter.create_histogram(
    name="data_processing_duration_seconds",
    description="Data processing duration in seconds",
    unit="s"
)

database_query_duration = meter.create_histogram(
    name="database_query_duration_seconds",
    description="Database query duration in seconds",
    unit="s"
)

external_api_duration = meter.create_histogram(
    name="external_api_duration_seconds",
    description="External API call duration in seconds",
    unit="s"
)

# ===== Flask アプリケーション初期化 =====
app = Flask(__name__)

# Flask インストルメンテーション
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

logger.info("Flask application initialized")


# ===== ビジネスロジック関数 =====

def simulate_database_query(user_id: int):
    """
    データベースクエリをシミュレート
    トレースとメトリクスでデータベース処理を追跡
    """
    with tracer.start_as_current_span("database_query") as span:
        start_time = time.time()
        
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.statement", "SELECT * FROM users WHERE id = ?")
        span.set_attribute("db.user_id", user_id)
        
        logger.info(f"Database query started for user_id: {user_id}")
        
        try:
            # クエリ遅延をシミュレート (0.05-0.2秒)
            query_time = random.uniform(0.05, 0.2)
            time.sleep(query_time)
            
            # メトリクスに記録
            duration = time.time() - start_time
            database_query_duration.record(duration, {"operation": "select", "table": "users"})
            
            # 結果を返す
            result = {
                "id": user_id,
                "name": f"User_{user_id}",
                "email": f"user{user_id}@example.com",
                "created_at": datetime.now().isoformat()
            }
            
            span.set_attribute("db.result_rows", 1)
            logger.info(f"Database query completed successfully")
            
            return result
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            logger.error(f"Database query failed: {str(e)}")
            raise


def simulate_external_api_call(endpoint: str):
    """
    外部 API 呼び出しをシミュレート
    トレースで外部依存を追跡
    """
    with tracer.start_as_current_span("external_api_call") as span:
        start_time = time.time()
        
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", endpoint)
        
        logger.info(f"External API call started: {endpoint}")
        
        try:
            # API 呼び出し遅延をシミュレート (0.1-0.5秒)
            api_time = random.uniform(0.1, 0.5)
            time.sleep(api_time)
            
            # ランダムにエラーを返す (20% の確率)
            if random.random() < 0.2:
                raise Exception("External API returned 500 Internal Server Error")
            
            duration = time.time() - start_time
            external_api_duration.record(duration, {"endpoint": endpoint})
            
            response = {
                "status": "success",
                "data": f"Response from {endpoint}",
                "timestamp": datetime.now().isoformat()
            }
            
            span.set_attribute("http.status_code", 200)
            logger.info(f"External API call completed successfully")
            
            return response
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("http.status_code", 500)
            span.set_attribute("error", True)
            logger.error(f"External API call failed: {str(e)}")
            raise


def process_user_data(user_id: int):
    """
    ユーザーデータ処理
    複数の子スパンを持つ親スパン
    """
    with tracer.start_as_current_span("process_user_data") as parent_span:
        start_time = time.time()
        
        parent_span.set_attribute("user.id", user_id)
        logger.info(f"User data processing started for user_id: {user_id}")
        
        try:
            # ステップ 1: データベースからユーザー情報を取得
            user_data = simulate_database_query(user_id)
            
            # ステップ 2: 外部 API からの追加情報を取得
            try:
                additional_data = simulate_external_api_call("https://api.example.com/user-details")
                user_data["additional_info"] = additional_data
            except Exception as e:
                logger.warning(f"Failed to fetch additional data: {str(e)}")
                user_data["additional_info"] = None
            
            # ステップ 3: データ変換・整形
            with tracer.start_as_current_span("data_transformation") as span:
                span.set_attribute("operation", "normalize")
                
                # データ変換処理（遅延をシミュレート）
                time.sleep(0.02)
                
                processed_data = {
                    **user_data,
                    "processed_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
                
                span.set_attribute("output.size", len(json.dumps(processed_data)))
            
            # メトリクスに記録
            duration = time.time() - start_time
            data_processing_duration.record(duration, {"operation": "full_processing"})
            
            logger.info(f"User data processing completed successfully")
            
            return processed_data
            
        except Exception as e:
            parent_span.record_exception(e)
            parent_span.set_attribute("error", True)
            logger.error(f"User data processing failed: {str(e)}")
            raise


# ===== Flask ルート =====

@app.route("/", methods=["GET"])
def hello():
    """ヘルスチェック用エンドポイント"""
    logger.info("GET / called")
    api_request_counter.add(1, {"endpoint": "/", "method": "GET"})
    
    return jsonify({
        "message": "Flask + OpenTelemetry Sample API",
        "version": "1.0",
        "endpoints": [
            "GET /health",
            "GET /user/<user_id>",
            "GET /simulate-error",
            "GET /performance-test"
        ]
    }), 200


@app.route("/health", methods=["GET"])
def health():
    """ヘルスチェックエンドポイント"""
    logger.info("GET /health called")
    api_request_counter.add(1, {"endpoint": "/health", "method": "GET"})
    
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


@app.route("/user/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    """
    ユーザーデータ取得エンドポイント
    トレース・メトリクス・ログの実例
    """
    start_time = time.time()
    
    logger.info(f"GET /user/{user_id} called")
    
    try:
        # ユーザーデータを処理
        user_data = process_user_data(user_id)
        
        # メトリクスに記録
        duration = time.time() - start_time
        api_request_counter.add(1, {"endpoint": "/user", "method": "GET", "status": "success"})
        api_request_duration.record(duration, {"endpoint": "/user", "status": "success"})
        
        logger.info(f"User {user_id} data returned successfully")
        
        return jsonify(user_data), 200
        
    except Exception as e:
        # エラー処理
        duration = time.time() - start_time
        api_error_counter.add(1, {"endpoint": "/user", "error_type": type(e).__name__})
        api_request_counter.add(1, {"endpoint": "/user", "method": "GET", "status": "error"})
        api_request_duration.record(duration, {"endpoint": "/user", "status": "error"})
        
        logger.error(f"Failed to get user {user_id}: {str(e)}", exc_info=True)
        
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route("/simulate-error", methods=["GET"])
def simulate_error():
    """
    意図的にエラーを発生させるエンドポイント
    トレースにおけるエラーハンドリングのデモンストレーション
    """
    logger.warning("GET /simulate-error called - intentional error")
    
    with tracer.start_as_current_span("simulated_error") as span:
        span.set_attribute("error.type", "intentional")
        
        try:
            # 意図的にエラーを発生
            raise ValueError("This is an intentional error for demonstration")
        except ValueError as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            
            api_error_counter.add(1, {"endpoint": "/simulate-error", "error_type": "ValueError"})
            
            logger.error(f"Intentional error: {str(e)}")
            
            return jsonify({
                "error": "Simulated Error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500


@app.route("/performance-test", methods=["GET"])
def performance_test():
    """
    パフォーマンステスト用エンドポイント
    複数のユーザーを処理して、パフォーマンスを測定
    """
    logger.info("GET /performance-test called")
    
    with tracer.start_as_current_span("performance_test") as span:
        start_time = time.time()
        
        try:
            # 複数ユーザーのデータを並行処理（シミュレーション）
            results = []
            for i in range(1, 4):
                with tracer.start_as_current_span(f"process_user_{i}"):
                    user_data = process_user_data(i)
                    results.append(user_data)
            
            duration = time.time() - start_time
            api_request_counter.add(1, {"endpoint": "/performance-test", "status": "success"})
            api_request_duration.record(duration, {"endpoint": "/performance-test"})
            
            logger.info(f"Performance test completed in {duration:.2f}s for 3 users")
            
            return jsonify({
                "test": "performance",
                "users_processed": 3,
                "total_duration_seconds": duration,
                "results": results
            }), 200
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            
            api_error_counter.add(1, {"endpoint": "/performance-test", "error_type": type(e).__name__})
            
            logger.error(f"Performance test failed: {str(e)}", exc_info=True)
            
            return jsonify({
                "error": "Performance test failed",
                "message": str(e)
            }), 500


@app.route("/metrics", methods=["GET"])
def get_metrics():
    """
    メトリクス確認用エンドポイント
    """
    logger.info("GET /metrics called")
    
    return jsonify({
        "message": "Metrics are available at http://otel-collector:8888/metrics",
        "endpoints": [
            "api_requests_total",
            "api_request_duration_seconds",
            "api_errors_total",
            "data_processing_duration_seconds",
            "database_query_duration_seconds",
            "external_api_duration_seconds"
        ]
    }), 200


# ===== エラーハンドラ =====

@app.errorhandler(404)
def not_found(error):
    """404 エラーハンドラ"""
    logger.warning(f"404 Not Found: {request.path}")
    api_error_counter.add(1, {"endpoint": "unknown", "error_type": "NotFound"})
    
    return jsonify({
        "error": "Not Found",
        "path": request.path,
        "timestamp": datetime.now().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """500 エラーハンドラ"""
    logger.error(f"500 Internal Server Error: {str(error)}", exc_info=True)
    api_error_counter.add(1, {"endpoint": "unknown", "error_type": "InternalServerError"})
    
    return jsonify({
        "error": "Internal Server Error",
        "timestamp": datetime.now().isoformat()
    }), 500


if __name__ == "__main__":
    logger.info("Starting Flask application on 0.0.0.0:3000")
    app.run(host="0.0.0.0", port=3000)