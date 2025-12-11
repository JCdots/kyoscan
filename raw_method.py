import requests
from urllib.parse import urlencode

def add_address_book_direct(printer_ip, entry_name, smb_address, smb_password='scanner#oki'):
    """Send direct POST to add SMB entry to address book."""
    url = f"https://{printer_ip}/basic/set.cgi"
    
    # Minimal form data for new SMB contact (addAbpPersonal mode)
    # Includes all hidden fields + SMB essentials; others empty for minimal.
    data = {
        # Routing/Hidden Fields (from form)
        'okhtmfile': '/basic/Contact_BasicRslt.htm',
        'failhtmfile': '/basic/Contact_BasicErr.htm',
        'func': 'addAbpPersonal',  # Add new personal contact
        'arg01_PageNum': '',  # Empty for new add
        'arg02_Sort': '0',
        'arg03_Search': '',
        'arg04_pageType': '0',  # Personal contacts
        'arg05_MemoryID': '',
        'arg12_SMBPassword': smb_password,  # Hidden password bind (duplicate visible one)
        'arg16_FTPPassword': '',  # Empty if no FTP
        'arg21_FCodePassword': '',  # Empty if no F-Code
        'arg50': '0',  # Non-JPN lang? (adjust if needed)
        'arg25_furi': '',  # Empty unless JPN
        'arg51': '0',
        'arg35': '1',
        'hidden': '',
        
        # Contact Fields (essentials for SMB)
        'arg06_sID': '',  # Auto-assigned number
        'arg07_Name': entry_name,
        'arg08_Email': '',  # Empty if no email
        'arg09_SMBAddress': smb_address,
        'arg38': '445',  # SMB port (default; adjust if custom)
        'arg10_SMBPathName': 'scanner',
        'arg11_SMBLoginName': 'scanner',
        'SMBPassword': smb_password,  # Visible password input
        
        # Other sections empty (FTP, FAX, etc.)
        'arg13_FTPAddress': '',
        'arg39': '',
        'arg14_FTPPathName': '', #21 default
        'arg15_FTPLoginName': '',
        'FTPPassword': '',
        'arg17_FAXNumber': '',
        'arg20_FCodeSubAddr': '',
        'arg18_BaudRate': '0',  # Default if FAX used
        'arg19_ECM': '0',  # Default if FAX used
        'arg22_EncryptionKey': '0',  # Default if encryption
        
        # Submit trigger (not always needed, but mimics button)
        'submit001': 'Enviar'
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0'  # Mimic browser
    }
    
    try:     
        # POST the data
        response = requests.post(url, data=urlencode(data), headers=headers, verify=False, timeout=10)
        
        # Debug: Print response
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Body: {response.text[:500]}...")  # Truncate for readability
        
        # Success check: Look for redirect or success HTML (customize based on response)
        if response.status_code == 200 and '/Contact_BasicRslt.htm' in response.text:
            return True, "Entry added successfully"
        else:
            return False, f"Failed: {response.status_code} - {response.text[:200]}"
    
    except requests.exceptions.RequestException as e:
        return False, f"Request error: {str(e)}"

# Example usage (integrate with your script)
success, msg = add_address_book_direct("192.168.11.253", "STI 9091", "192.168.11.235")
print(f"Result: {success} - {msg}")