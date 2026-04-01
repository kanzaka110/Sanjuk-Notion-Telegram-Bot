import os 
import yfinance as yf
import requests
from datetime import datetime

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

def get_notion_pages():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers)
    if response.status_code != 200:
        return []
        
    results = response.json().get("results", [])
    pages = []
    
    for page in results:
        page_id = page["id"]
        props = page.get("properties", {})
        prop_data = props.get("매매종목", {})
        prop_type = prop_data.get("type", "")
        
        ticker = ""
        if prop_type == "rich_text":
            text_arr = prop_data.get("rich_text", [])
            if text_arr: ticker = text_arr[0].get("plain_text", "")
        elif prop_type == "title":
            text_arr = prop_data.get("title", [])
            if text_arr: ticker = text_arr[0].get("plain_text", "")
        elif prop_type == "select":
            select_data = prop_data.get("select")
            if select_data: ticker = select_data.get("name", "")
        elif prop_type == "formula":
            formula_data = prop_data.get("formula", {})
            if formula_data.get("type") == "string": 
                ticker = formula_data.get("string", "")
                
        ticker = ticker.strip()
        if ticker:
            pages.append({"id": page_id, "ticker": ticker})
                
    return pages

def get_exchange_rate():
    try:
        rate_data = yf.Ticker("USDKRW=X").history(period="1d")
        if not rate_data.empty:
            return float(rate_data['Close'].iloc[-1])
    except:
        pass
    return 1400.0

def get_stock_price(ticker):
    yf_ticker = ticker
    if ticker.startswith("KRX:"):
        yf_ticker = ticker.replace("KRX:", "") + ".KS"
        
    stock = yf.Ticker(yf_ticker)
    hist = stock.history(period="1d")
    
    if hist.empty:
        return None
        
    return float(hist['Close'].iloc[-1])

def update_notion_prices(page_id, formatted_original_price, final_krw_price):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    payload = {
        "properties": {
            "현재가": {
                "rich_text": [{"text": {"content": formatted_original_price}}]
            },
            "원화가격": {
                "number": final_krw_price
            }
        }
    }
    requests.patch(url, headers=headers, json=payload)

if __name__ == "__main__":
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 자동 업데이트 시작")
    
    exchange_rate = get_exchange_rate()
    pages = get_notion_pages()
    
    for page in pages:
        ticker = page["ticker"]
        page_id = page["id"]
        
        current_price = get_stock_price(ticker)
        
        if current_price is not None:
            if ticker.startswith("KRX:"):
                original_price = int(current_price)
                final_krw_price = int(current_price)
                formatted_original_price = f"₩{original_price:,}"
            else:
                original_price = round(current_price, 2)
                final_krw_price = int(current_price * exchange_rate)
                formatted_original_price = f"${original_price:,.2f}"
            
            update_notion_prices(page_id, formatted_original_price, final_krw_price)
            
    print("업데이트 완료")
