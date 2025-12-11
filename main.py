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

def get_printer_hostname(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/startwlm/Start_Wlm.model.htm"
    
    headers = {
        "Referer": f"https://{ip_address}/startwlm/Start_Wlm.htm",
        "Cookie": "rtl=0; css=1"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        match = re.search(r"_pp\.f_getHostName\s*=\s*'([^']*)';", response.text)
        if match:
            return match.group(1)
        else:
            return None
            
    except Exception as e:
        return None

def get_printer_toner_level(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/startwlm/Hme_Toner.model.htm"
    
    headers = {
        "Referer": f"https://{ip_address}/startwlm/Hme_Toner.htm",
        "Cookie": "rtl=0; css=1"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        matches = re.findall(r"_pp\.Renaming\.push\(parseInt\('(\d+)',\s*10\)\);", response.text)
        
        if matches:
            return int(matches[0])
        else:
            return None

    except Exception as e:
        return None

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
        return {'Name': name, 'IP': None, 'Hostname': "N/A", 'Toner': "N/A"}
    
    # Fetch data
    hostname = get_printer_hostname(ip)
    toner = get_printer_toner_level(ip)
    
    return {'Name': name, 'IP': ip, 'Hostname': hostname, 'Toner': toner}

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
                    print(f"Progress: {i + 1}/{len(printer_dict)}")
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
            print(f"Printer Name: {data['Name']}, IP: {data['IP']}, Hostname: {f'{data['Hostname']}' if data['Hostname'] is not None else 'N/A'}, Toner Level: {f'{data['Toner']}%' if data['Toner'] is not None else 'N/A'}")

    # printers = get_printers_from_server(server_ip)
    # sorted_printers = sort_printers_by_ip(printers)

    # print("Printers and their IPs:")
    # for name, ip_addr in sorted_printers.items():
    #     print(f"{name}: {ip_addr}")

    # print("Total printers found:", len(printers))