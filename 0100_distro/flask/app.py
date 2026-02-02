from flask import Flask
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)

# これだけでFlaskの全ルートが自動的にトレース対象になります
FlaskInstrumentor().instrument_app(app)

@app.route("/")
def hello():
    return "Hello from Flask with OTel!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)