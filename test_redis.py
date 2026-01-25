import os
import redis
from dotenv import load_dotenv

load_dotenv()

# Test Upstash Redis connection
redis_url = os.getenv('REDIS_URL')

if not redis_url:
    print("❌ REDIS_URL not found in environment variables")
    exit(1)

try:
    print(f"Testing connection to: {redis_url}")
    
    # Connect to Upstash Redis
    r = redis.from_url(redis_url)
    
    # Test ping
    response = r.ping()
    print(f"✅ Redis ping response: {response}")
    
    # Test set/get
    r.set('test_key', 'Hello from Django!')
    value = r.get('test_key')
    print(f"✅ Set/Get test successful: {value.decode('utf-8')}")
    
    # Clean up
    r.delete('test_key')
    
    print("✅ All Redis tests passed!")
    
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    import traceback
    traceback.print_exc()