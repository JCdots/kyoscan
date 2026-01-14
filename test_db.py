from database import Database
from config import Config
import sys

def get_mock_printer_data():
    """Generate fake printer data for testing."""
    return [
        {
            "Name": "KM-Test-01",
            "IP": "10.0.0.100",
            "Hostname": "printer123456",
            "Serial": "TESTSERIAL123456",
            "Mac": "00:11:22:33:44:57",
            "Status": "Online",
            "Toner": 80,
            "Print_Data": {"copy_bw": 100, "printer_bw": 200, "fax_bw": 5},
            "Scan_Data": {"scan_copy": 50, "scan_bw": 20, "scan_other": 10}
        },
        {
            "Name": "KM-Test-Offline",
            "IP": None,
            "Hostname": "N/A",
            "Serial": None,
            "Mac": None,
            "Status": "Offline",
            "Toner": None,
            "Print_Data": None,
            "Scan_Data": None
        },
        {
            "Name": "KM-Test-LowToner",
            "IP": "10.0.0.101",
            "Hostname": "printer-low-toner",
            "Serial": "ALERTSERIAL999",
            "Mac": "AA:BB:CC:DD:EE:FG",
            "Status": "Offline",
            "Toner": 5, 
            "Print_Data": {"copy_bw": 5000, "printer_bw": 2000, "fax_bw": 100},
            "Scan_Data": {}
        }
    ]

def run_test():
    print("=== Starting Database Test ===")
    
    # 1. Inspect Config
    config = Config()
    db_conf = config.get_db_config()
    
    print("Checking Configuration:")
    for key, value in db_conf.items():
        # mask password for display
        display_val = "******" if key == "password" else value
        print(f"  {key}: {display_val} (Type: {type(value)})")

    # 2. Test Connection
    try:
        with Database(config) as db:
            if db.conn is None:
                print("❌ Connection failed immediately after initialization.")
                sys.exit(1)
                
            print("✔ Connection successful (Object created)")
            
            # 2. Mock Data
            mock_data = get_mock_printer_data()
            print(f"Prepared {len(mock_data)} mock records.")
            
            # 3. Save Data
            print("Attempting to save data...")
            db.save_printer_data(mock_data)
            
            # 4. Verification
            with db.conn.cursor() as cur:
                # Check Devices
                cur.execute("SELECT COUNT(*) FROM devices WHERE serial_number LIKE 'TEST%' OR serial_number LIKE 'ALERT%'")
                count = cur.fetchone()[0]
                print(f"✔ Devices table: Found {count} test devices")

                # Check Logs
                cur.execute("SELECT COUNT(*) FROM device_logs")
                log_count = cur.fetchone()[0]
                print(f"✔ Logs table: Found {log_count} total logs")

                # Check Alert View
                cur.execute("SELECT device_name, toner_alert FROM devices_alert_view WHERE toner_level < 10")
                alert_row = cur.fetchone()
                if alert_row:
                    print(f"✔ Alert View: Found low toner alert for {alert_row[0]}")
                else:
                    print("✘ Alert View: Failed to find low toner alert")

    except Exception as e:
        print(f"❌ Test Failed with Exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    run_test()