import win32print
import requests
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_printers_from_server(server_ip):
    """
    Connects to a Windows Print Server via win32print (Spooler API) and retrieves printers.
    Parses the 'Comment' field to extract the first valid IP address.
    """
    printer_dict = {}
    
    # Regex to find the first IPv4 address in a string
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

    try:
        print(f"Connecting to Print Spooler on {server_ip}...")
        
        # Use win32print.EnumPrinters (Level 1) as seen in main.py
        # This uses the Spooler service RPC which is often more accessible than WMI
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_NAME,
            f'\\\\{server_ip}',
            1
        )

        for printer_info in printers:
            print(printer_info)
            # Handle potential tuple vs dict return (robustness from main.py)
            if isinstance(printer_info, tuple):
                # Level 1 tuple: (Flags, Description, Name, Comment)
                flags, description, name, comment = printer_info
            else:
                name = printer_info.get('pPrinterName', '')
                comment = printer_info.get('pComment', '')

            # Clean up name (remove \\Server\)
            if '\\' in name:
                name = name.split('\\')[-1]
            
            if comment:
                # Search for the first IP address in the comment string
                match = ip_pattern.search(comment)
                if match:
                    ip_address = match.group(0)
                    printer_dict[name] = ip_address
                else:
                    # Handle cases where comment exists but has no IP
                    printer_dict[name] = None
            else:
                # Handle cases with no comment
                printer_dict[name] = None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    return printer_dict

def get_printer_hostname(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/startwlm/Start_Wlm.model.htm"
    
    headers = {
        "Referer": f"https://{ip_address}/startwlm/Start_Wlm.htm",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Cookie": "rtl=0; css=1"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        match = re.search(r"_pp\.f_getHostName\s*=\s*'([^']*)';", response.text)
        if match:
            return match.group(1)
        else:
            return "Hostname not found"
            
    except Exception as e:
        return f"Error fetching hostname: {e}"

def get_printer_toner_level(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/startwlm/Hme_Toner.model.htm"
    
    headers = {
        "Referer": f"https://{ip_address}/startwlm/Hme_Toner.htm", 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Cookie": "rtl=0; css=1"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        matches = re.findall(r"_pp\.Renaming\.push\(parseInt\('(\d+)',\s*10\)\);", response.text)
        
        if matches:
            return int(matches[0])
        else:
            return "Toner level not found"

    except Exception as e:
        return f"Error fetching toner: {e}"
    
if __name__ == "__main__":
    ip = "192.168.11.253"
    server_ip = "10.3.3.10"

    printers = get_printers_from_server(server_ip)
    # print("Printers and their IPs:")
    # for name, ip_addr in printers.items():
    #     print(f"{name}: {ip_addr}")

    # print("Total printers found:", len(printers))

    hostname = get_printer_hostname(ip)
    toner_level = get_printer_toner_level(ip)
    print(f"Printer Hostname: {hostname}")
    print(f"Toner Level: {toner_level}%")