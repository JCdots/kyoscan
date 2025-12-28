import win32print
import requests
import re
import urllib3
import concurrent.futures

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

        # Optimize loop by unpacking the tuple directly: (Flags, Description, Name, Comment)
        for flags, description, name, comment in printers:
            # Clean up name (remove \\Server\)
            if name and '\\' in name:
                clean_name = name.split('\\')[-1]
            else:
                clean_name = name
            
            if comment:
                # Search for the first IP address in the comment string
                match = ip_pattern.search(comment)
                if match:
                    printer_dict[clean_name] = match.group(0)
                else:
                    printer_dict[clean_name] = None
            else:
                printer_dict[clean_name] = None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

    return printer_dict

def get_printer_info(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/dvcinfo/dvcconfig/DvcConfig_Config.model.htm?arg1=0"
    
    headers = {
        "Referer": f"https://{ip_address}/dvcinfo/dvcconfig/DvcConfig_Config.htm?arg1=0",
        "Cookie": "rtl=0; css=1"
    }
    
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status()

    info = {}
    patterns = {
        "hostname": r"_pp\.hostName\s*=\s*'([^']*)';",
        "serial": r"_pp\.serialNumber\s*=\s*'([^']*)';",
        "mac": r"_pp\.macAddress\s*=\s*'([^']*)';"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, response.text)
        if match:
            info[key] = match.group(1)
        else:
            info[key] = None

    return info

def get_printer_toner_level(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/startwlm/Hme_Toner.model.htm"
    
    headers = {
        "Referer": f"https://{ip_address}/startwlm/Hme_Toner.htm",
        "Cookie": "rtl=0; css=1"
    }
    
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status()

    matches = re.findall(r"_pp\.Renaming\.push\(parseInt\('(\d+)',\s*10\)\);", response.text)

    if matches:
        return int(matches[0])
    else:
        return None

def get_printer_print_data(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/dvcinfo/dvccounter/DvcInfo_Counter_PrnCounter.model.htm"

    headers = {
        "Referer": f"https://{ip_address}/dvcinfo/dvccounter/DvcInfo_Counter_PrnCounter.htm",
        "Cookie": "rtl=0; css=1"
    }

    response = requests.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status()

    data = {}
    patterns = {
        "copy_bw": r"_pp\.copyBlackWhite\s*=\s*\('(\d+)'\)\.toString\(\);",
        "printer_bw": r"_pp\.printerBlackWhite\s*=\s*\('(\d+)'\)\.toString\(\);",
        "fax_bw": r"_pp\.faxBlackWhite\s*=\s*\('(\d+)'\)\.toString\(\);"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, response.text)
        if match:
            data[key] = int(match.group(1))
        else:
            data[key] = None

    return data

def get_printer_scan_data(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/dvcinfo/dvccounter/DvcInfo_Counter_ScanCounter.model.htm"

    headers = {
        "Referer": f"https://{ip_address}/dvcinfo/dvccounter/DvcInfo_Counter_ScanCounter.htm",
        "Cookie": "rtl=0; css=1"
    }

    response = requests.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status()

    data = {}
    patterns = {
        "scan_copy": r"_pp\.scanCopy\s*=\s*parseInt\('(\d+)',\s*10\);",
        "scan_bw": r"_pp\.scanBlackWhite\s*=\s*parseInt\('(\d+)',\s*10\);",
        "scan_other": r"_pp\.scanOther\s*=\s*parseInt\('(\d+)',\s*10\);"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, response.text)
        if match:
            data[key] = int(match.group(1))
        else:
            data[key] = None

    return data

def sort_printers_by_ip(printer_dict):
    """
    Sorts the printer dictionary by IP address.
    Printers with no IP are placed at the end.
    """
    def ip_sort_key(item):
        ip = item[1]
        if ip:
            try:
                # Convert IP string "192.168.1.1" to tuple (192, 168, 1, 1) for proper numeric sorting
                return tuple(map(int, ip.split('.')))
            except ValueError:
                pass
        # Return a tuple that ensures these come last
        return (float('inf'),)

    return dict(sorted(printer_dict.items(), key=ip_sort_key))

def fetch_printer_details(name, ip):
    """Helper to fetch details for a single printer safely."""
    if not ip:
        return {'Name': name, 'IP': None, 'Hostname': "N/A", 'Serial': None, 'Mac': None, 'Toner': "N/A", 'Status': "Offline"}
    
    hostname = None
    serial = None
    mac = None
    toner = None
    is_online = False

    # Fetch data
    try:
        info = get_printer_info(ip)
        hostname = info.get('hostname')
        serial = info.get('serial')
        mac = info.get('mac')
        is_online = True
    except Exception:
        pass

    try:
        toner = get_printer_toner_level(ip)
        is_online = True
    except Exception:
        toner = None

    try:
        print_data = get_printer_print_data(ip)
        is_online = True
    except Exception:
        print_data = None
    
    try:
        scan_data = get_printer_scan_data(ip)
        is_online = True
    except Exception:
        scan_data = None

    status = "Online" if is_online else "Offline"
    
    return {'Name': name, 'IP': ip, 'Hostname': hostname, 'Serial': serial, 'Mac': mac, 'Toner': toner, 'Print_Data': print_data, 'Scan_Data': scan_data, 'Status': status}

def get_all_printers_data(printer_dict, max_workers=50):
    """
    Fetches hostname and toner level for all printers concurrently.
    """
    results = []
    print(f"Starting concurrent fetch for {len(printer_dict)} printers with {max_workers} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks
        future_to_printer = {
            executor.submit(fetch_printer_details, name, ip): name 
            for name, ip in printer_dict.items()
        }
        
        # Collect results
        for i, future in enumerate(concurrent.futures.as_completed(future_to_printer)):
            try:
                data = future.result()
                results.append(data)
                if (i + 1) % 10 == 0:
                    print(f"Progress: {i + 1}/{len(printer_dict)}", end='\r')
            except Exception as exc:
                print(f"Task generated an exception: {exc}")
                
    return results


if __name__ == "__main__":
    server_ip = "10.3.3.10"

    # 1. Get printers from server
    printers = get_printers_from_server(server_ip)

    if printers:
        # 2. Fetch details concurrently
        all_data = get_all_printers_data(printers)
        sorted_data = sorted(all_data, key=lambda x: (tuple(map(int, x['IP'].split('.'))) if x['IP'] else (float('inf'),)))
        # 3. Print results
        for data in sorted_data:
            print(f"Printer Name: {data['Name']}, IP: {data['IP']}, Hostname: {f'{data['Hostname']}' if data['Hostname'] is not None else 'N/A'}, Serial: {f'{data['Serial']}' if data['Serial'] is not None else 'N/A'}, Mac: {f'{data['Mac']}' if data['Mac'] is not None else 'N/A'}, Toner Level: {f'{data['Toner']}%' if data['Toner'] is not None else 'N/A'}, Print Data: {data['Print_Data'] if data['Print_Data'] is not None else 'N/A'}, Scan Data: {data['Scan_Data'] if data['Scan_Data'] is not None else 'N/A'}, Status: {data['Status']}")