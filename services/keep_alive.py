import asyncio
import httpx
import time
from ..core.config import settings
from ..core.logging import logger
from ..core.mailer import notify_server_wake, notify_error

# Global variable to track the last ping time to prevent excessive self-pings
_last_ping_time = 0

async def ping_self():
    """
    Bg task that pings the server's own health endpoint.
    """
    global _last_ping_time
    
    url = settings.RENDER_EXTERNAL_URL
    if not url:
        logger.warning("RENDER_EXTERNAL_URL not set. Keep-alive system inactive.")
        return

    # Ensure URL ends with /health/ping
    ping_url = f"{url.rstrip('/')}/health/ping"
    interval = settings.KEEP_ALIVE_INTERVAL_MINUTES * 60

    # Send wake notification once on startup
    logger.info("Keep-alive service starting. Sending wake notification...")
    notify_server_wake()

    while True:
        try:
            current_time = time.time()
            
            # Cooldown mechanism: ensure at least 4 minutes passed between pings 
            # (even if interval is set higher, this prevents rapid restarts from spamming)
            if current_time - _last_ping_time < 240:
                logger.debug("Ping skipped due to cooldown mechanism.")
            else:
                async with httpx.AsyncClient() as client:
                    logger.info(f"Sending keep-alive ping to {ping_url}")
                    response = await client.get(ping_url, timeout=10.0)
                    
                    if response.status_code == 200:
                        logger.info("Keep-alive ping successful.")
                        _last_ping_time = current_time
                    else:
                        logger.error(f"Keep-alive ping failed with status {response.status_code}")
                        notify_error(f"Keep-alive ping failed with status {response.status_code}")

        except Exception as e:
            logger.error(f"Keep-alive system error: {e}")
            notify_error(f"Keep-alive system error: {str(e)}")

        # Wait for the next interval
        await asyncio.sleep(interval)

def start_keep_alive():
    """
    Starts the keep-alive background task.
    """
    asyncio.create_task(ping_self())
