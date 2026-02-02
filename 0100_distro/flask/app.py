from flask import Flask
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)

FlaskInstrumentor().instrument_app(app)
tracer = trace.get_tracer(__name__)


@app.route("/")
def hello():
    with tracer.start_as_current_span("hello-handler"):
        return "Hello from Flask with OTel!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
