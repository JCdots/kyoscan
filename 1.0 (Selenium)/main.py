import subprocess
import os
import socket
import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException

def check_printer_ip_range(printer_ip, low=240, high=254):
    """Check if IP falls within the specified range."""
    try:
        host_id = int(printer_ip.split(".")[3])
        return low <= host_id <= high
    except (IndexError, ValueError):
        return False

def ping_host(iphost, timeout=5):
    """Ping an IP address or hostname and return True if reachable."""
    param = "-n" if os.name == "nt" else "-c"
    command = ["ping", param, "1", iphost]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def resolve_and_ping(hostname, expected_ip=None, timeout=5):
    """Resolve hostname to IP and optionally verify it matches expected IP, then ping."""
    try:
        resolved_ip = socket.gethostbyname(hostname)
        if expected_ip and resolved_ip != expected_ip:
            return False, f"Resolved IP {resolved_ip} does not match expected {expected_ip}."
        if not ping_host(resolved_ip, timeout):
            return False, f"Ping to {resolved_ip} failed."
        return True, "Resolved and reachable."
    except socket.gaierror:
        return False, "Hostname resolution failed."

def is_folder_shared(remote_host, folder_name="scanner"):
    """Check if folder is shared on remote host."""
    try:
        result = subprocess.run(['net', 'view', f'\\\\{remote_host}'], capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"Failed to query {remote_host}: {result.stderr.strip()}."

        for line in result.stdout.splitlines():
            if folder_name.lower() in line.lower():
                return True, f"Folder '{folder_name}' is shared on {remote_host}."
        return False, f"Folder '{folder_name}' is not shared on {remote_host}."
    except Exception as e:
        return False, f"Error checking shared folder: {e}."

def permission_result(read=False, write=False, message=""):
    """Helper to format permission check results."""
    return {"Read": read, "Write": write, "Message": message}

def get_folder_permissions(iphost, folder_name="scanner"):
    """Check read/write permissions for 'Everyone' on shared folder."""
    folder_path = f"\\\\{iphost}\\{folder_name}"

    try:
        result = subprocess.run(['icacls', folder_path], capture_output=True, text=True)
        if result.returncode != 0:
            return permission_result(False, False, f"Failed to access folder: {result.stderr.strip()}.")

        read_flags = {"R", "RX", "F", "M"}
        write_flags = {"W", "F", "M"}
        read = write = False

        for line in result.stdout.splitlines():
            if "Everyone" in line:
                perms = set(line.split(":")[-1])
                read = bool(read_flags & perms)
                write = bool(write_flags & perms)
                break

        return permission_result(read, write, "Permissions parsed successfully.")

    except Exception as e:
        return permission_result(False, False, f"Error checking permissions: {e}.")

def automate_address_book_addition(printer_ip, entry_name, smb_address, smb_password='scanner#oki', timeout=15):
    edge_options = Options()
    edge_options.add_argument("--disable-logging")
    edge_options.add_argument("--log-level=3")
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    edge_options.add_experimental_option('useAutomationExtension', False)
    edge_options.accept_insecure_certs = True
    # edge_options.add_argument("--headless")

    driver = webdriver.Edge(options=edge_options)
    wait = WebDriverWait(driver, timeout)

    try:
        # Step 1: Open printer web interface
        driver.get(f"https://{printer_ip}/")
        driver.set_window_size(1346, 708)

        # Step 2: Switch to main frame
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "wlmframe")))

        # Step 3: Click Address Book menu
        address_book_menu = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".AddressBook > .P001_menu_main_caption")))
        address_book_menu.click()
        
        # Step 4: Click sub-menu
        sub_menu = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#s17 > p")))
        sub_menu.click()
        
        # Step 5: Switch to inner frame
        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "wlmframe")))
        driver.switch_to.frame(1)
        
        # Step 6: Click Add button
        add_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".button:nth-child(2) img")))
        add_button.click()
        
        # Step 7: Switch back to parent frame, then to index=0
        driver.switch_to.parent_frame()
        driver.switch_to.frame(0)
        
        # Step 8: Fill form fields
        wait.until(EC.presence_of_element_located((By.NAME, 'arg07_Name'))).send_keys(entry_name)
        ID = driver.find_element(By.NAME, 'arg06_sID').get_attribute("value")
        driver.find_element(By.ID, 'arg09_SMBAddress').send_keys(smb_address)
        driver.find_element(By.ID, 'arg10_SMBPathName').send_keys('scanner')
        driver.find_element(By.ID, 'arg11_SMBLoginName').send_keys('scanner')
        print(ID)


        # Step 10: Submit the form directly via JS to bypass onclick issues
        form = driver.find_element(By.NAME, 'adrscontact')
        driver.execute_script("arguments[0].submit();", form)
        

    except Exception as e:
        driver.save_screenshot('debug_error.png')
        return False, f"Selenium error: {str(e)}", None

    finally:
        driver.quit()

success, message, entry = automate_address_book_addition("192.168.11.253", "STI 9091", "192.168.11.235")

print("Success:", success)
print("Message:", message)

print(is_folder_shared("192.168.11.231"))