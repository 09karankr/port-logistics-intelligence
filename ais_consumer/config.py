import os
from dotenv import load_dotenv

load_dotenv()

AISSTREAM_API_KEY = os.environ["AISSTREAM_API_KEY"]
AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Focused on European/Atlantic waters where free-tier AIS data is dense.
# Satellite AIS (Pacific/Indian Ocean) requires a paid aisstream.io plan.
# Format: [[min_lon, min_lat], [max_lon, max_lat]]
BOUNDING_BOXES = [
    # North Sea + English Channel (highest vessel density in the world)
    [[-5, 48], [10, 62]],
    # Baltic Sea
    [[9, 53], [30, 66]],
    # North Atlantic (Europe ↔ US East Coast transatlantic lane)
    [[-60, 35], [0, 60]],
    # Mediterranean Sea (west)
    [[-6, 30], [20, 46]],
    # Mediterranean Sea (east) + Suez Canal
    [[20, 28], [42, 42]],
    # West Africa / Gulf of Guinea
    [[-20, -10], [10, 10]],
    # US East Coast + Gulf of Mexico
    [[-100, 18], [-60, 48]],
    # Caribbean
    [[-90, 8], [-55, 28]],
]

# Track ALL vessel types — maximises vessel count from available data.
# Set to empty to disable filtering (track everything).
TRACKED_VESSEL_TYPES: set[int] = set()

# DB batch insert every N messages or M seconds (whichever first)
BATCH_SIZE = 50
BATCH_TIMEOUT_SECONDS = 5

# Publish live positions to Redis pub/sub channel for API WebSocket
REDIS_POSITIONS_CHANNEL = "vessel:positions:live"
