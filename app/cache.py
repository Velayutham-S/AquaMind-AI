import json
import time
from app.config import Config
from app.logging_config import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class MemoryCache:
    """Fallback in-memory cache with TTL support."""
    def __init__(self):
        self._store = {}
        logger.info("Local in-memory cache fallback initialized.")

    def get(self, key):
        if key not in self._store:
            return None
        val, expiry = self._store[key]
        if expiry is not None and time.time() > expiry:
            del self._store[key]
            return None
        return val

    def set(self, key, value, ex=None):
        expiry = time.time() + ex if ex is not None else None
        self._store[key] = (value, expiry)
        return True

    def delete(self, key):
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self):
        self._store.clear()
        return True

class CacheClient:
    def __init__(self):
        self.client = None
        self.is_redis = False
        
        if REDIS_AVAILABLE:
            try:
                self.client = redis.Redis(
                    host=Config.REDIS_HOST,
                    port=Config.REDIS_PORT,
                    db=0,
                    socket_connect_timeout=2,
                    decode_responses=True
                )
                # Test connection
                self.client.ping()
                self.is_redis = True
                logger.info(f"Connected to Redis cache at {Config.REDIS_HOST}:{Config.REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Falling back to in-memory cache.")
                self.client = MemoryCache()
        else:
            logger.info("Redis package not installed. Using in-memory cache.")
            self.client = MemoryCache()

    def get(self, key: str):
        """Retrieve key from cache. Handles JSON decoding automatically."""
        try:
            val = self.client.get(key)
            if val is not None:
                try:
                    return json.loads(val)
                except ValueError:
                    return val
            return None
        except Exception as e:
            logger.error(f"Error reading from cache key {key}: {e}")
            return None

    def set(self, key: str, value, ex: int = 3600):
        """Store value in cache with an expiration timeout (in seconds)."""
        try:
            serialized = json.dumps(value)
            if self.is_redis:
                self.client.set(key, serialized, ex=ex)
            else:
                self.client.set(key, serialized, ex=ex)
            return True
        except Exception as e:
            logger.error(f"Error writing to cache key {key}: {e}")
            return False

    def delete(self, key: str):
        """Delete key from cache."""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

# Export global cache client singleton
cache = CacheClient()
