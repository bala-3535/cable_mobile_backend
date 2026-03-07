import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_system():
    print("--- Starting Cable Service System Validation ---")
    
    # 1. Check Root
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Root Check: {response.status_code}, {response.json()}")
    except Exception as e:
        print(f"Error connecting to server: {e}")
        print("Make sure the server is running with 'uvicorn app.main:app --reload'")
        return

    print("\nNext steps for manual verification in Swagger UI (/docs):")
    print("1. Create first Admin via database or a temporary open endpoint (currently all protected).")
    print("2. Login at /users/login to get JWT.")
    print("3. Use Admin JWT to create Agents at /users/.")
    print("4. Use Admin JWT to create Customers at /customers/.")
    print("5. Use Agent JWT to update payments at /customers/payment/{id}.")
    print("6. Verify Agent cannot delete customers.")

if __name__ == "__main__":
    test_system()
