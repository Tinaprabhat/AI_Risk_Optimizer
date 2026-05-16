from app.core.redis import redis_client

redis_client.set("test", "working")

print(redis_client.get("test"))