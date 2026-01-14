import asyncio
import httpx
import win32print
import re
from typing import Dict, List, Optional, Any

def get_printers_from_server(server_ip: str) -> Optional[Dict[str, Optional[str]]]:
    """Retrieve printers from the print server and extract IPs."""
    printer_dict = {}
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

    try:
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_NAME, f'\\\\{server_ip}', 1)

        for flags, description, name, comment in printers:
            clean_name = name.split('\\')[-1] if name and '\\' in name else name
            ip = None
            if comment:
                match = ip_pattern.search(comment)
                ip = match.group(0) if match else None
            printer_dict[clean_name] = ip

    except Exception as e:
        print(f"Error: {e}")
        return None

    return printer_dict

async def fetch_printer_data(client: httpx.AsyncClient, ip: str, endpoint: str, headers: Dict[str, str]) -> str:
    """Generic function to fetch data from a printer endpoint."""
    url = f"https://{ip}{endpoint}"
    response = await client.get(url, headers=headers)
    response.raise_for_status()
    return response.text

async def parse_printer_info(text: str) -> Dict[str, Optional[str]]:
    """Parse hostname, serial, and MAC from response text."""
    patterns = {
        "hostname": r"_pp\.hostName\s*=\s*'([^']*)';",
        "serial": r"_pp\.serialNumber\s*=\s*'([^']*)';",
        "mac": r"_pp\.macAddress\s*=\s*'([^']*)';"
    }
    return {key: (re.search(pattern, text).group(1) if re.search(pattern, text) else None) for key, pattern in patterns.items()}

async def parse_toner_level(text: str) -> Optional[int]:
    """Parse toner level from response text."""
    matches = re.findall(r"_pp\.Renaming\.push\(parseInt\('(\d+)',\s*10\)\);", text)
    return int(matches[0]) if matches else None

async def parse_counter_data(text: str, patterns: Dict[str, str]) -> Dict[str, Optional[int]]:
    """Parse counter data using given patterns."""
    return {key: (int(match.group(1)) if (match := re.search(pattern, text)) else None) for key, pattern in patterns.items()}

async def fetch_printer_details(client: httpx.AsyncClient, name: str, ip: Optional[str], semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    """Fetch all details for a single printer."""
    async with semaphore:
        if not ip:
            return {'Name': name, 'IP': None, 'Hostname': "N/A", 'Serial': None, 'Mac': None, 'Toner': None, 'Print_Data': None, 'Scan_Data': None, 'Status': "Offline"}
        
        info = {'Name': name, 'IP': ip, 'Hostname': None, 'Serial': None, 'Mac': None, 'Toner': None, 'Print_Data': None, 'Scan_Data': None, 'Status': "Offline"}
        
        try:
            # Fetch basic info
            headers = {"Referer": f"https://{ip}/dvcinfo/dvcconfig/DvcConfig_Config.htm?arg1=0", "Cookie": "rtl=0; css=1"}
            text = await fetch_printer_data(client, ip, "/js/jssrc/model/dvcinfo/dvcconfig/DvcConfig_Config.model.htm?arg1=0", headers)
            parsed_info = await parse_printer_info(text)
            info.update({'Hostname': parsed_info['hostname'], 'Serial': parsed_info['serial'], 'Mac': parsed_info['mac'], 'Status': "Online"})
            
            # Fetch toner
            headers = {"Referer": f"https://{ip}/startwlm/Hme_Toner.htm", "Cookie": "rtl=0; css=1"}
            text = await fetch_printer_data(client, ip, "/js/jssrc/model/startwlm/Hme_Toner.model.htm", headers)
            info['Toner'] = await parse_toner_level(text)
            
            # Fetch print data
            headers = {"Referer": f"https://{ip}/dvcinfo/dvccounter/DvcInfo_Counter_PrnCounter.htm", "Cookie": "rtl=0; css=1"}
            text = await fetch_printer_data(client, ip, "/js/jssrc/model/dvcinfo/dvccounter/DvcInfo_Counter_PrnCounter.model.htm", headers)
            patterns = {
                "copy_bw": r"_pp\.copyBlackWhite\s*=\s*\('(\d+)'\)\.toString\(\);",
                "printer_bw": r"_pp\.printerBlackWhite\s*=\s*\('(\d+)'\)\.toString\(\);",
                "fax_bw": r"_pp\.faxBlackWhite\s*=\s*\('(\d+)'\)\.toString\(\);"
            }
            info['Print_Data'] = await parse_counter_data(text, patterns)
            
            # Fetch scan data
            headers = {"Referer": f"https://{ip}/dvcinfo/dvccounter/DvcInfo_Counter_ScanCounter.htm", "Cookie": "rtl=0; css=1"}
            text = await fetch_printer_data(client, ip, "/js/jssrc/model/dvcinfo/dvccounter/DvcInfo_Counter_ScanCounter.model.htm", headers)
            patterns = {
                "scan_copy": r"_pp\.scanCopy\s*=\s*parseInt\('(\d+)',\s*10\);",
                "scan_bw": r"_pp\.scanBlackWhite\s*=\s*parseInt\('(\d+)',\s*10\);",
                "scan_other": r"_pp\.scanOther\s*=\s*parseInt\('(\d+)',\s*10\);"
            }
            info['Scan_Data'] = await parse_counter_data(text, patterns)
            
        except Exception:
            pass
        
        return info

async def get_all_printers_data_async(printer_dict: Dict[str, Optional[str]], max_concurrent: int = 20) -> List[Dict[str, Any]]:
    """Fetch data for all printers concurrently."""
    
    semaphore = asyncio.Semaphore(max_concurrent)
    limits = httpx.Limits(max_keepalive_connections=max_concurrent, max_connections=max_concurrent)
    
    async with httpx.AsyncClient(verify=False, timeout=10.0, limits=limits) as client:
        tasks = [fetch_printer_details(client, name, ip, semaphore) for name, ip in printer_dict.items()]
        
        results = []
        total = len(tasks)
        
        # Progress marker: update every 10 printers
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            results.append(result)
            if (i + 1) % 10 == 0 or (i + 1) == total:
                print(f"Progress: {i + 1}/{total} printers processed.", end='\r')
        
        return results

async def main() -> None:
    """Main entry point."""
    server_ip = "10.3.3.10"
    printers = get_printers_from_server(server_ip)
    
    if printers:
        all_data = await get_all_printers_data_async(printers)
        for data in all_data:
            print(data)

if __name__ == "__main__":
    asyncio.run(main())