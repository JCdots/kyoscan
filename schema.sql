CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    serial_number VARCHAR(50) UNIQUE NOT NULL,
    mac_address VARCHAR(17),
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS device_history (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_name VARCHAR(255),
    ip_address INET,
    mac_address VARCHAR(17),
    hostname VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS device_logs (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20),
    toner_level SMALLINT,
    printer_copy_bw INTEGER,
    printer_printer_bw INTEGER,
    printer_fax_bw INTEGER,
    scanner_copy INTEGER,
    scanner_bw INTEGER,
    scanner_other INTEGER
);

CREATE TABLE IF NOT EXISTS device_current_state (
    device_id INTEGER PRIMARY KEY REFERENCES devices(id),
    device_name VARCHAR(255),
    ip_address INET,
    mac_address VARCHAR(17),
    hostname VARCHAR(255),
    status VARCHAR(20),
    toner_level SMALLINT,
    printer_copy_bw INTEGER,
    printer_printer_bw INTEGER,
    printer_fax_bw INTEGER,
    scanner_copy INTEGER,
    scanner_bw INTEGER,
    scanner_other INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    toner_alert BOOLEAN DEFAULT FALSE,
    offline_alert BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_history_device_time ON device_history(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_history_device_timestamp ON device_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_device_time ON device_logs(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_device_timestamp ON device_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_current_toner ON device_current_state(toner_level) WHERE toner_level IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_current_status ON device_current_state(status);

CREATE OR REPLACE VIEW devices_alert_view AS
SELECT
    d.serial_number,
    dcs.device_name,
    dcs.ip_address::text,
    dcs.hostname,
    dcs.toner_level,
    dcs.status,
    dcs.last_updated,
    CASE
        WHEN dcs.toner_level IS NOT NULL AND dcs.toner_level < 10 THEN TRUE
        ELSE FALSE
    END AS toner_alert,
    CASE
        WHEN dcs.status = 'Offline' THEN TRUE
        ELSE FALSE
    END AS offline_alert
FROM device_current_state dcs
JOIN devices d ON d.id = dcs.device_id
WHERE (dcs.toner_level IS NOT NULL AND dcs.toner_level < 10) OR dcs.status = 'Offline';