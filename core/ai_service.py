import google.generativeai as genai
import json
import pandas as pd
import io
from typing import List, Dict, Any
from core.config import settings
from schemas import CustomerCreate, ConnectionType, AccountStatus

def process_file_data(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Processes Excel or CSV data using Gemini to identify column mapping,
    then applies that mapping to all rows using Pandas.
    """
    if not settings.GOOGLE_API_KEY:
        raise Exception("GOOGLE_API_KEY not configured")

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')

    # 1. Read file into DataFrame
    try:
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            df = pd.read_excel(io.BytesIO(file_content))
    except Exception as e:
        raise Exception(f"Failed to read file: {str(e)}")

    headers = df.columns.tolist()
    sample_data = df.head(5).to_dict(orient='records')

    # 2. Ask AI for the MAPPING schema
    prompt = f"""
    I have a spreadsheet with these headers: {headers}
    Sample data (first 5 rows): {json.dumps(sample_data, default=str)}

    I need a JSON 'mapping' object to import this into our system. 
    Our system fields are:
    - account_number (string, required)
    - customer_name (string, required)
    - address (string, required)
    - phone_number (string, required)
    - box_detail (string, optional)
    - subscription_plan (string, required)
    - connection_type (must be exactly 'cable' or 'internet')
    - billing_day (integer 1-31, required)
    - amount_paid (number, optional, default 0)
    - balance_due (number, optional, default 0)
    - account_status (must be exactly 'active', 'suspended', or 'inactive')

    Please return a JSON object with two keys:
    1. "column_mapping": A dictionary where keys are OUR system fields and values are the EXACT column headers from the spreadsheet.
    2. "defaults": A dictionary of default values for fields that might be missing or need specific values (e.g., "connection_type": "cable", "billing_day": 1, "account_status": "active").

    Only return the JSON object, no explanation.
    """

    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.endswith("```"): text = text[:-3]
    text = text.strip()

    try:
        mapping_result = json.loads(text)
        column_mapping = mapping_result.get("column_mapping", {})
        defaults = mapping_result.get("defaults", {})
    except Exception as e:
        print(f"Failed to parse AI mapping response: {text}")
        raise Exception("AI failed to identify data mapping")

    # 3. Apply mapping to ALL rows using Pandas
    mapped_results = []
    
    # Fill NaN values to avoid issues
    df = df.where(pd.notnull(df), None)

    for _, row in df.iterrows():
        customer_row = {}
        
        # Apply mapping from identified columns
        for system_field, excel_col in column_mapping.items():
            if excel_col in row:
                val = row[excel_col]
                # Light cleanup
                if isinstance(val, str):
                    val = val.strip()
                customer_row[system_field] = val

        # Fill in defaults for missing required fields
        for field, default_val in defaults.items():
            if field not in customer_row or customer_row[field] is None:
                customer_row[field] = default_val

        # Final safety checks for required fields/enums
        if not customer_row.get('account_number'): continue # Skip rows without account numbers
        
        # Ensure enums are valid or use defaults
        status = str(customer_row.get('account_status', 'active')).strip().lower()
        if status not in ['active', 'suspended', 'inactive']:
            customer_row['account_status'] = 'active'
        else:
            customer_row['account_status'] = status
            
        conn_type = str(customer_row.get('connection_type', 'cable')).strip().lower()
        if 'internet' in conn_type:
            customer_row['connection_type'] = 'internet'
        else:
            customer_row['connection_type'] = 'cable'

        # Ensure numeric types
        try:
            customer_row['billing_day'] = int(float(customer_row.get('billing_day', 1)))
            if not (1 <= customer_row['billing_day'] <= 31): customer_row['billing_day'] = 1
        except:
            customer_row['billing_day'] = 1

        try:
            customer_row['amount_paid'] = float(customer_row.get('amount_paid', 0))
        except:
            customer_row['amount_paid'] = 0.0

        try:
            customer_row['balance_due'] = float(customer_row.get('balance_due', 0))
        except:
            customer_row['balance_due'] = 0.0

        mapped_results.append(customer_row)

    return mapped_results

def generate_admin_insight(data: Dict[str, Any]) -> str:
    """
    Generates a high-level summary and business insight for the admin dashboard.
    """
    if not settings.GOOGLE_API_KEY:
        return "AI analysis unavailable (API key not set)."

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = f"""
    You are a business analyst for a Cable and Internet service provider.
    Based on the following real-time data, provide a concise (max 3-4 sentences) professional insight summary for the Admin dashboard.
    Focus on collection performance, unpaid ratios, and identifying which areas need attention.

    Current Data:
    - Total Customers: {data['total_customers']}
    - Total Outstanding Balance: ₹{data['total_due']:,}
    - No. of Unpaid Customers: {data['unpaid_count']}
    - Area-wise Performance: {json.dumps(data['area_performance'])}
    - Recent Activity: {json.dumps(data['recent_activity'])}

    Be direct, helpful, and professional. Structure as a single paragraph.
    """

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            return "Monthly AI insight limit reached. We'll have a new analysis for you soon! High-level stats are still available above."
        return f"Admin Insight is currently being updated. Please check back in a moment."
