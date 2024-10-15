import requests
from base64 import b64encode
from src.config import *

def scan_komga_library(library_id):
    if not komga_ip or not komga_login_email or not komga_login_password:
        print("Komga settings are not properly configured. Please check your settings.py file.")
        return

    komga_url = f"{komga_ip}:{komga_port}" if komga_port else komga_ip

    print(f"\nSending Komga Scan Request for library {library_id}:")
    try:
        auth = b64encode(f"{komga_login_email}:{komga_login_password}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "*/*",
        }
        
        response = requests.post(
            f"{komga_url}/api/v1/libraries/{library_id}/scan",
            headers=headers,
        )
        
        if response.status_code == 202:
            print(f"\tSuccessfully Initiated Scan for: {library_id} Library.")
        else:
            print(f"\tFailed to Initiate Scan for: {library_id} Library. Status Code: {response.status_code}")
            print(f"\tResponse: {response.text}")
    except Exception as e:
        print(f"Failed to Initiate Scan for: {library_id} Komga Library, ERROR: {e}")

def get_komga_libraries(first_run=True):
    if not komga_ip or not komga_login_email or not komga_login_password:
        print("Komga settings are not properly configured. Please check your settings.py file.")
        return []

    komga_url = f"{komga_ip}:{komga_port}" if komga_port else komga_ip

    try:
        auth = b64encode(f"{komga_login_email}:{komga_login_password}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "*/*",
        }
        
        response = requests.get(
            f"{komga_url}/api/v1/libraries",
            headers=headers,
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\tFailed to Get Komga Libraries. Status Code: {response.status_code}")
            print(f"\tResponse: {response.text}")
            return []
    except Exception as e:
        if first_run and "104" in str(e):
            print("Connection error. Retrying in 60 seconds...")
            time.sleep(60)
            return get_komga_libraries(first_run=False)
        else:
            print(f"Failed to Get Komga Libraries, ERROR: {e}")
            return []
