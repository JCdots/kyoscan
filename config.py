import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ### Authentication
    NETWORK_USER = os.getenv("NETWORK_USER", "DOMAIN\\username")
    NETWORK_PASSWORD = os.getenv("NETWORK_PASSWORD", "password")

    ### Database
    DB_NAME = os.getenv("DB_NAME", "kyoscan")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_USER = os.getenv("DB_USER", "user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

    ### Print Server
    PRINT_SERVER_IP = os.getenv("PRINT_SERVER_IP", "10.3.3.10")

    ### Async Performance
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 5.0))

    ### Alerting
    ALERT_TONER_THRESHOLD = int(os.getenv("ALERT_TONER_THRESHOLD", 10))
    ALERT_OFFLINE_HOURS = int(os.getenv('ALERT_OFFLINE_HOURS', 48))

    @classmethod
    def get_db_config(cls):
        """
        Get database configuration parameters.
        
        :param cls: Class reference
        :return: Dictionary with database connection parameters.
        """
        return {
            "database": cls.DB_NAME,
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
        }