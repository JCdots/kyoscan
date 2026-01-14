import psycopg2
import re
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from config import Config

class Database:
    def __init__(self, config: Config):
        self.config = config.get_db_config()
        self.conn = None
    
    def connect(self):
        """Establish a connection to the PostgreSQL database."""

        if not self.conn or self.conn.closed:
            try:
                self.conn = psycopg2.connect(
                    dbname=self.config["database"],
                    host=self.config["host"],
                    port=self.config["port"],
                    user=self.config["user"],
                    password=self.config["password"]
                )
            except Exception as e:
                print(f"Database connection error: {e}")
                self.conn = None
    
    def close(self):
        """Close the database connection."""

        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.close()
    
    def resolve_device_id(self, cursor, serial: Optional[str], name: str | Any, 
                          ip: Optional[str], hostname: Optional[str], 
                          mac: Optional[str], timestamp: datetime) -> Optional[int]:
        """
        Resolve device ID from database, inserting or updating as needed.
        
        :param cursor: Database cursor
        :param serial: Serial number
        :param name: Device name
        :param ip: IP address
        :param hostname: Hostname
        :param mac: MAC address
        :return: Device ID or None if unable to resolve
        """

        device_db_id = None

        if serial:
            cursor.execute("""
                            SELECT id
                            FROM devices
                            WHERE serial_number = %s
                            """, (serial,))
            result_row = cursor.fetchone()

            if result_row:
                device_db_id = result_row[0]
                if mac:
                    cursor.execute("""
                                    UPDATE devices
                                    SET mac_address = %s
                                    WHERE id = %s
                                    """, (mac, device_db_id))
            
            else:
                cursor.execute("""
                                INSERT INTO devices (serial_number, mac_address, first_seen)
                                VALUES (%s, %s, %s)
                                RETURNING id
                                """, (serial, mac, timestamp))
                device_db_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                            SELECT device_id
                            FROM device_history
                            WHERE device_name = %s
                            ORDER BY timestamp DESC LIMIT 1
                            """, (name,))
            result_row = cursor.fetchone()

            if result_row:
                device_db_id = result_row[0]
                
        return device_db_id
    
    def should_update_config(self, cursor, device_id: int, name: str | Any, 
                            ip: Optional[str], mac: Optional[str], hostname: Optional[str]) -> bool:
        """
        Check if device configuration has changed since last recorded.
        
        :param cursor: Database cursor
        :param device_id: Device ID
        :param name: Current device name
        :param ip: Current IP address
        :param hostname: Current hostname
        :param mac: Current MAC address
        :return: True if config should be updated
        """

        cursor.execute("""
            SELECT device_name, ip_address::text, hostname, mac_address
            FROM device_history 
            WHERE device_id = %s 
            ORDER BY timestamp DESC LIMIT 1
        """, (device_id,))

        last_config = cursor.fetchone()
        
        if not last_config:
            return True
        
        last_name, last_ip, last_hostname, last_mac = last_config

        ## Handle /32 suffix from Postgres INET type
        ip_changed = False
        if ip and last_ip:
            clean_last_ip = last_ip.split('/')[0] # Remove /32 if present
            ip_changed = (ip != clean_last_ip)
        elif bool(ip) != bool(last_ip): # One is None, the other isn't
            ip_changed = True

        hostname_changed = (hostname is not None and hostname != last_hostname)
        mac_changed = (mac is not None and mac != last_mac)

        return (name != last_name) or ip_changed or hostname_changed or mac_changed
    
    def save_printer_data(self, data_list: List[Dict[str, Any]]):
        """
        Save printer data to PostgreSQL database.
        
        This method:
        1. Resolves printer IDs (insert new or match existing)
        2. Updates configuration history when changes detected
        3. Logs usage data (toner, counters)
        4. Updates current state table with alerts
        
        :param data_list: List of printer data dictionaries
        """

        if not self.conn or self.conn.closed:
            print("Database connection is not established.")
            return
        
        cursor = self.conn.cursor()
        timestamp = datetime.now()
        saved_count = 0
        not_resolved = []

        try:
            for data in data_list:
                serial = data.get('Serial')
                name = data.get('Name')
                ip = data.get('IP')
                hostname = data.get('Hostname')
                mac = data.get('Mac')
                print_data = data.get('Print_Data') or {}
                scan_data = data.get('Scan_Data') or {}

                device_id = self.resolve_device_id(
                    cursor,
                    serial,
                    name,
                    ip,
                    hostname,
                    mac,
                    timestamp
                )

                if not device_id:
                    not_resolved.append(name)
                    continue

                if self.should_update_config(
                    cursor,
                    device_id,
                    name,
                    ip,
                    mac,
                    hostname
                ):
                    cursor.execute("""
                        INSERT INTO device_history (device_id, device_name, ip_address, mac_address, hostname, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        device_id,
                        name,
                        ip,
                        mac,
                        hostname,
                        timestamp
                    ))

                cursor.execute("""
                    INSERT INTO device_logs (
                        device_id, timestamp, status, toner_level,
                        printer_copy_bw, printer_printer_bw, printer_fax_bw,
                        scanner_copy, scanner_bw, scanner_other
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        device_id, timestamp, data.get('Status'), data.get('Toner'),
                        print_data.get('copy_bw'), print_data.get('printer_bw'), print_data.get('fax_bw'),
                        scan_data.get('scan_copy'), scan_data.get('scan_bw'), scan_data.get('scan_other')
                    ))
                
                toner_alert = data.get('Toner') is not None and data.get('Toner') < Config.ALERT_TONER_THRESHOLD
                offline_alert = data.get('Status') == 'Offline'
                
                cursor.execute("""
                    INSERT INTO device_current_state (
                        device_id, device_name, ip_address, mac_address, hostname, status, toner_level,
                        printer_copy_bw, printer_printer_bw, printer_fax_bw,
                        scanner_copy, scanner_bw, scanner_other, last_updated,
                        toner_alert, offline_alert
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        device_name = EXCLUDED.device_name,
                        ip_address = EXCLUDED.ip_address,
                        mac_address = EXCLUDED.mac_address,
                        hostname = EXCLUDED.hostname,
                        status = EXCLUDED.status,
                        toner_level = EXCLUDED.toner_level,
                        printer_copy_bw = EXCLUDED.printer_copy_bw,
                        printer_printer_bw = EXCLUDED.printer_printer_bw,
                        printer_fax_bw = EXCLUDED.printer_fax_bw,
                        scanner_copy = EXCLUDED.scanner_copy,
                        scanner_bw = EXCLUDED.scanner_bw,
                        scanner_other = EXCLUDED.scanner_other,
                        last_updated = EXCLUDED.last_updated,
                        toner_alert = EXCLUDED.toner_alert,
                        offline_alert = EXCLUDED.offline_alert
                """, (
                    device_id, name, ip, mac, hostname, data['Status'], data.get('Toner'),
                    print_data.get('copy_bw'), print_data.get('printer_bw'), print_data.get('fax_bw'),
                    scan_data.get('scan_copy'), scan_data.get('scan_bw'), scan_data.get('scan_other'),
                    timestamp, toner_alert, offline_alert
                ))

                saved_count += 1
            
            self.conn.commit()
            print(f"\nSaved data for {saved_count} printers.")
            print(f"Could not resolve device IDs for {len(not_resolved)} printers.")
            
        except Exception as e:
            self.conn.rollback()
            print(f"Error saving printer data: {e}")
            raise
        finally:
            cursor.close()