import time
import random
import logging
from flask import Flask, jsonify, request

from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode

# =========================
# Tracer / Meter
# =========================
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# ---- custom metrics ----
request_counter = meter.create_counter(
    name="app_requests_total",
    description="Total number of requests",
)

error_counter = meter.create_counter(
    name="app_errors_total",
    description="Total number of errors",
)

processing_time = meter.create_histogram(
    name="app_processing_time_ms",
    description="Processing time in ms",
)

# =========================
# Flask app
# =========================
app = Flask(__name__)

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()


# =========================
# Fake internal functions
# =========================
def fake_db_query(user_id: int):
    with tracer.start_as_current_span("db.query") as span:
        time.sleep(random.uniform(0.05, 0.2))
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.user_id", user_id)

        if user_id == 13:
            raise RuntimeError("DB connection failed")

        return {"user_id": user_id, "name": "alice"}


def fake_external_api():
    with tracer.start_as_current_span("external.api.call") as span:
        latency = random.uniform(0.1, 0.4)
        time.sleep(latency)
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", "https://example.com/api")
        span.set_attribute("latency", latency)

        if random.random() < 0.3:
            raise TimeoutError("External API timeout")

        return {"result": "ok"}


# =========================
# Routes
# =========================
@app.route("/")
def hello():
    start = time.time()

    request_counter.add(1, {"endpoint": "/"})
    logging.info("hello endpoint called")

    with tracer.start_as_current_span("business.logic") as span:
        time.sleep(0.05)
        span.set_attribute("logic.step", "greeting")

    processing_time.record((time.time() - start) * 1000)
    return {"message": "Hello from Flask!"}


@app.route("/user/<int:user_id>")
def get_user(user_id: int):
    start = time.time()
    request_counter.add(1, {"endpoint": "/user"})

    try:
        user = fake_db_query(user_id)
        api_result = fake_external_api()

        return jsonify({
            "user": user,
            "external": api_result,
        })

    except Exception as e:
        error_counter.add(1, {"endpoint": "/user"})
        logging.exception("failed to handle /user request")

        span = trace.get_current_span()
        span.record_exception(e)
        span.set_status(Status(StatusCode.ERROR, str(e)))

        return jsonify({"error": str(e)}), 500

    finally:
        processing_time.record(
            (time.time() - start) * 1000,
            {"endpoint": "/user"},
        )


@app.route("/health")
def health():
    request_counter.add(1, {"endpoint": "/health"})
    return {"status": "ok"}


# =========================
# Entry point
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)