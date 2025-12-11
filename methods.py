# Solved by
# Jean C. S. Moura
# Pablo Nicolay
# 2025

import requests
from urllib.parse import urlencode
import re
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suppress InsecureRequestWarning for clean output
warnings.simplefilter('ignore', InsecureRequestWarning)

def fetch_available_id(printer_ip, proxies=None):
    """
    Fetch and parse the first available contact ID from the printer's model.
    """
    model_url = (
        f"https://{printer_ip}/js/jssrc/model/basic/AddrBook_Addr_NewCntct_Prpty.model.htm"
        f"?arg1=1&arg2=0&arg3=&arg4=0&arg5=&arg6=1&arg50=0"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Referer': f'https://{printer_ip}/basic/AddrBook_Addr_NewCntct_Prpty.htm?arg1=1&arg2=0&arg3=&arg4=0&arg5=&arg6=1&arg50=0',
        'Cookie': 'rtl=0'
    }
    
    try:
        response = requests.get(model_url, headers=headers, proxies=proxies, verify=False, timeout=10)
        if response.status_code != 200:
            return None
        
        # Extract emptyMemoryId with regex (lightweight, no full JS eval)
        match = re.search(r"_pp\.emptyMemoryId\s*=\s*'([^']+)';", response.text)
        if not match:
            return None
        
        # Split and return first available ID
        ids = [id.strip() for id in match.group(1).split('/') if id.strip()]
        return ids[0] if ids else None
        
    except (requests.RequestException, IndexError):
        return None

def fetch_address_book_page(printer_ip, page=1, proxies=None):
    """
    Fetch a page of the address book entries.
    Returns (total_entries: int, page_entries: list of {'id': str, 'name': str})
    """
    list_url = (
        f"https://{printer_ip}/js/jssrc/model/basic/AddrBook_Addr.model.htm"
        f"?arg1={page}&arg2=0&arg3=&arg4=1&arg5=&arg6=0&arg7=0&arg8=&arg9=&arg50=0"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Referer': f'https://{printer_ip}/basic/AddrBook_Addr.htm?arg1={page}&arg2=0&arg3=&arg4=1&arg5=&arg6=0&arg7=0&arg9=&arg50=0',
        'Cookie': 'rtl=0'
    }
    
    try:
        response = requests.get(list_url, headers=headers, proxies=proxies, verify=False, timeout=10)
        if response.status_code != 200:
            return 0, []
        
        # Extract total
        match_total = re.search(r"_pp\.TotsearchResult\s*=\s*'([^']+)';", response.text)
        total = int(match_total.group(1)) if match_total else 0
        
        # Extract list count
        match_listcount = re.search(r"_pp\.h_getAbpListCount\s*=\s*'([^']+)';", response.text)
        list_count = int(match_listcount.group(1)) if match_listcount else 0
        
        # Extract IDs and names using findall (order preserved)
        ids = re.findall(r"_pp\.AddrNumber\s*\[index\]\s*=\s*'([^']+)';", response.text)
        names_raw = re.findall(r"_pp\.AddrType\s*\[index\]\s*=\s*'([^']+)';", response.text)
        
        entries = []
        for idx in range(min(len(ids), len(names_raw))):
            entry_id = ids[idx]
            entry_name = names_raw[idx]  # Original name before any replacement
            entries.append({'id': entry_id, 'name': entry_name})
        
        return total, entries
        
    except (requests.RequestException, ValueError, IndexError):
        return 0, []

def get_all_entries(printer_ip, proxies=None):
    """
    Fetch all address book entries by paginating through pages.
    Returns list of {'id': str, 'name': str}
    """
    all_entries = []
    page = 1
    total = 0
    
    while True:
        page_total, page_entries = fetch_address_book_page(printer_ip, page, proxies)
        total = page_total  # Update total from first page
        if not page_entries:
            break
        all_entries.extend(page_entries)
        if len(all_entries) >= total:
            break
        page += 1
    
    return all_entries[:total]  # Trim if overfetched

def fetch_entry_detail(printer_ip, entry_id, proxies=None):
    """
    Fetch details for a specific entry ID.
    Returns (success: bool, number: str, name: str, smb_host: str or None)
    """
    detail_url = (
        f"https://{printer_ip}/js/jssrc/model/basic/AddrBook_Addr_NewCntct_Prpty.model.htm"
        f"?arg1=1&arg2=0&arg3=&arg4=1&arg5={entry_id}&arg6=1&arg50=0"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Referer': f'https://{printer_ip}/basic/AddrBook_Addr_NewCntct_Prpty.htm?arg1=1&arg2=0&arg3=&arg4=1&arg5={entry_id}&arg6=1&arg50=0',
        'Cookie': 'rtl=0'
    }
    
    try:
        response = requests.get(detail_url, headers=headers, proxies=proxies, verify=False, timeout=10)
        if response.status_code != 200:
            return False, None, None, None
        
        match_number = re.search(r"_pp\.number\s*=\s*'([^']+)';", response.text)
        number = match_number.group(1) if match_number else None
        
        match_name = re.search(r"_pp\.nameAdbk\s*=\s*'([^']*)';", response.text)
        name = match_name.group(1) if match_name else None
        
        match_smb = re.search(r"_pp\.smbHostName\s*=\s*'([^']*)';", response.text)
        smb_host = match_smb.group(1).strip() if match_smb else None
        
        if number and name:  # Valid entry
            return True, number, name, smb_host
        return False, None, None, None
        
    except requests.RequestException:
        return False, None, None, None

def check_duplicates(printer_ip, target_smb_ip, proxies=None):
    """
    Check for duplicate SMB entries matching the target IP.
    Returns list of {'id': str, 'name': str} for duplicates.
    """
    entries = get_all_entries(printer_ip, proxies)
    duplicates = []
    
    for entry in entries:
        success, number, name, smb_host = fetch_entry_detail(printer_ip, entry['id'], proxies)
        if success and smb_host and smb_host == target_smb_ip:
            duplicates.append({'id': number, 'name': name})
    
    return duplicates

def delete_entry(printer_ip, entry_id, proxies=None):
    """
    Delete a specified entry from the printer's address book.
    Returns (success: bool, message: str, response_text: str or None)
    """
    cgi_url = f"https://{printer_ip}/basic/set.cgi"
    
    # Form data for deletion
    form_data = {
        'okhtmfile': '/basic/Contact_BasicDelRslt.htm',
        'failhtmfile': '/basic/Contact_BasicErr.htm',
        'func': 'deleteAbpPersonalGroup',
        'arg01_PageNum': '1',
        'arg02_Sort': '0',
        'arg03_Search': '',
        'arg04_MemoryIDNum': '1',
        'arg05_AIIID': '0',
        'arg06_MemoryID': '',
        'arg07_MemoryID': '',
        'arg08_MemoryID': '',
        'arg09_MemoryID': '',
        'arg10_MemoryID': '',
        'arg11_MemoryID': '',
        'arg12_MemoryID': '',
        'arg13_MemoryID': '',
        'arg14_MemoryID': '',
        'arg15_MemoryID': '',
        'arg17_Filtertpe': '',
        'hidden': '',
        'arg16_ID': entry_id,
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.9',
        'Cookie': 'rtl=0'
    }
    
    try:
        response = requests.post(
            cgi_url, data=urlencode(form_data), headers=headers,
            proxies=proxies, verify=False, timeout=10
        )
        
        # Debug: Print status and response preview
        print(f"Delete response for ID {entry_id}: Status {response.status_code}")
        
        # For delete, success if status 200 (no progress gif needed, as delete is immediate)
        if response.status_code != 200:
            return False, f"Delete failed HTTP {response.status_code}", response.text
        
        return True, f"Successfully deleted entry with ID: {entry_id}", response.text
        
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}", None

def cleanup_duplicates(printer_ip, target_smb_ip, proxies=None):
    """
    Retrieve duplicates for the target SMB IP, delete all except the one with the smallest ID,
    and return the details of the kept entry.
    Returns {'success': bool, 'kept_id': str or None, 'entry_name': str or None, 'smb_address': str or None, 'message': str}
    """
    # Retrieve duplicates
    duplicates = check_duplicates(printer_ip, target_smb_ip, proxies)
    if not duplicates:
        return {
            'success': False,
            'kept_id': None,
            'entry_name': None,
            'smb_address': None,
            'message': 'No duplicates found.'
        }
    
    # Find the duplicate with the smallest ID (convert to int for comparison)
    min_dup = min(duplicates, key=lambda x: int(x['id']))
    min_id = min_dup['id']
    
    # Delete all other duplicates
    deleted_count = 0
    for dup in duplicates:
        if dup['id'] != min_id:
            success, msg, resp_text = delete_entry(printer_ip, dup['id'], proxies)
            if success:
                deleted_count += 1
            else:
                # Log error but continue
                print(f"Failed to delete duplicate ID {dup['id']}: {msg}")
                if resp_text:
                    print(f"Response for failed delete: {resp_text[:200]}...")
    
    # Fetch details of the kept entry
    success, number, name, smb_host = fetch_entry_detail(printer_ip, min_id, proxies)
    if success and smb_host == target_smb_ip:
        return {
            'success': True,
            'kept_id': number,
            'entry_name': name,
            'smb_address': smb_host,
            'message': f'Cleaned up {len(duplicates) - 1} duplicates. Kept ID: {number}'
        }
    else:
        return {
            'success': False,
            'kept_id': None,
            'entry_name': None,
            'smb_address': None,
            'message': 'Failed to fetch details of kept entry after cleanup.'
        }

def add_smb_contact(printer_ip, smb_address, smb_password='scanner#oki', proxies=None, check_duplicates_first=True):
    """
    Add an SMB contact to the printer's address book.
    Optionally checks for duplicates first.
    Returns (success: bool, id: str or error: str, response_text: str or None, duplicates: list or None)
    """
    if check_duplicates_first:
        dups = check_duplicates(printer_ip, smb_address, proxies)
        if dups:
            return False, f"Duplicates found: {dups}", None, dups
    
    # Fetch ID inline (single call, no separate function overhead)
    available_id = fetch_available_id(printer_ip, proxies)
    if not available_id:
        return False, "Failed to fetch available ID", None, None
    
    cgi_url = f"https://{printer_ip}/basic/set.cgi"
    entry_name = '.'.join(smb_address.split('.')[2:])
    
    # Minimal form data: Only required fields for SMB add (from captured traffic)
    form_data = {
        'okhtmfile': '/basic/Contact_BasicRslt.htm',
        'failhtmfile': '/basic/Contact_BasicErr.htm',
        'func': 'addAbpPersonal',
        'arg01_PageNum': '',
        'arg02_Sort': '0',
        'arg03_Search': '',
        'arg04_pageType': '0',
        'arg05_MemoryID': '',
        'arg12_SMBPassword': smb_password,
        'arg16_FTPPassword': '',
        'arg21_FCodePassword': '',
        'arg50': '0',
        'arg25_furi': '',
        'arg51': '0',
        'arg35': '1',
        'hidden': '',
        'arg06_sID': available_id,
        'arg07_Name': entry_name,
        'arg08_Email': '',
        'arg09_SMBAddress': smb_address,
        'arg38': '445',
        'arg10_SMBPathName': 'scanner',
        'arg11_SMBLoginName': 'scanner',
        'SMBPassword': smb_password,
        'arg13_FTPAddress': '',
        'arg39': '21',
        'arg14_FTPPathName': '',
        'arg15_FTPLoginName': '',
        'FTPPassword': '',
        'arg17_FAXNumber': '',
        'arg20_FCodeSubAddr': '',
        'arg18_BaudRate': '0',
        'arg19_ECM': '1',
        'arg22_EncryptionKey': '0',
        'submit001': 'Enviar'
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.9',
        'Referer': f'https://{printer_ip}/basic/AddrBook_Addr_NewCntct_Prpty.htm?arg1=1&arg2=0&arg3=&arg4=0&arg5=&arg6=1&arg50=0',
        'Cookie': 'rtl=0'
    }
    
    try:
        response = requests.post(
            cgi_url, data=urlencode(form_data), headers=headers,
            proxies=proxies, verify=False, timeout=10
        )
        
        if response.status_code != 200 or 'Progress_1.gif' not in response.text:
            return False, "Add failed (unexpected response)", response.text, None
        
        return True, available_id, response.text, None
        
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)}", None, None

def get_printer_hostname(ip_address):
    url = f"https://{ip_address}/js/jssrc/model/startwlm/Start_Wlm.model.htm"
    
    # Headers based on your and 
    headers = {
        "Referer": f"https://{ip_address}/startwlm/Start_Wlm.htm",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Cookie": "rtl=0; css=1" # Added cookie from source 2
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
    
    # Headers based on your 
    # Note: The Referer here is slightly different (Hme_Toner.htm vs Start_Wlm.htm)
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

# if __name__ == "__main__":
#     # Example: Check for duplicates
#     duplicates = check_duplicates(
#         printer_ip="192.168.186.249",
#         target_smb_ip="192.168.186.54",
#         proxies=None  # No proxy
#     )
#     if duplicates:
#         print("Duplicates found:")
#         for dup in duplicates:
#             print(f"ID: {dup['id']}, Name: {dup['name']}")
#     else:
#         print("No duplicates found.")

#     # Example: Cleanup duplicates (with logging enabled)
#     result = cleanup_duplicates(
#         printer_ip="192.168.11.253",
#         target_smb_ip="192.168.11.235",
#         proxies=None  # No proxy
#     )
#     if result['success']:
#         print(f"Kept ID: {result['kept_id']}, Name: {result['entry_name']}, SMB: {result['smb_address']}")
#         print(result['message'])
#     else:
#         print(f"Cleanup failed: {result['message']}")
    
    # add_smb_contact(
    #     '192.168.186.249', '192.168.186.54'
    # )

    # hostname = get_printer_hostname('192.168.11.253')
    # toner = get_printer_toner_level('192.168.11.253')
    
    # print(f"Printer: {hostname}")
    # print(f"Toner Level: {toner}%")