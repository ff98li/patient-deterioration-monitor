"""
Combined Consumer + Dashboard API

This script runs both the Kafka consumer and the Flask API in the same process,
so they share the same in-memory state.
"""

import threading
from consumer_multistream import main as consumer_main, create_consumer, consume_multistream
from dashboard_api import app
import shared_state


def run_flask():
    """Run Flask API in a separate thread."""
    # Disable Flask's reloader since we're running in a thread
    app.run(host='0.0.0.0', port=5050, debug=False, threaded=True, use_reloader=False)


def main():
    print("=" * 70)
    print("Patient Deterioration Monitor - Combined Consumer + API")
    print("=" * 70)
    
    # Start Flask API in background thread
    print("\n🌐 Starting Dashboard API on port 5050...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✓ Dashboard API started")
    
    # Run consumer in main thread
    print("\n📡 Starting Kafka Consumer...")
    consumer = create_consumer()
    print(f"✓ Connected to Confluent Cloud")
    
    consume_multistream(consumer)


if __name__ == "__main__":
    main()
