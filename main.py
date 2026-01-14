from config import Config
from database import Database
from fetcher import get_printers_from_server, get_all_printers_data_async
from logger import get_logger
import asyncio

async def main() -> None:
    """Main entry point."""
    logger = get_logger()
    logger.info("Starting Kyoscan data pipeline.")
   
    ### Fetch printers from print server
    printers = get_printers_from_server(Config.PRINT_SERVER_IP)
    
    if not printers:
        logger.error("No printers found or connection error to printer server occurred.")
        return
    
    ### Fetch printer metrics asynchronously
    all_data = await get_all_printers_data_async(
        printers, 
        max_concurrent=Config.MAX_CONCURRENT_REQUESTS
    )
    
    ### Save results to database
    with Database(Config()) as db:
        db.save_printer_data(all_data)
    
    logger.info("Kyoscan data pipeline completed.")

if __name__ == "__main__":
    asyncio.run(main())