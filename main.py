from config import Config
from database import Database
from fetcher import get_printers_from_server, get_all_printers_data_async
import asyncio

async def main() -> None:
    """Main entry point."""
   
    ### Fetch printers from print server
    printers = get_printers_from_server(Config.PRINT_SERVER_IP)
    
    if not printers:
        print("No printers found or connection error occurred.")
        return
    
    ### Fetch printer metrics asynchronously
    all_data = await get_all_printers_data_async(
        printers, 
        max_concurrent=Config.MAX_CONCURRENT_REQUESTS
    )
    
    ### Save results to database (with context manager)
    with Database(Config()) as db:
        db.save_printer_data(all_data)
        
    print("\n✓ Pipeline completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())