import json
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import yfinance as yf
from datetime import datetime

PORTFOLIO_FILE = 'portfolio.json'
STOCKS_FILE = 'stocks_data.json'
INITIAL_CASH = 10000.0
POSITION_LIMIT = 0.20
MARKET_INDEX = "^GSPC"

# Gmail 發信函數
def send_email_alert(subject, content):
    mail_user = os.environ.get('MAIL_USER')
    mail_pass = os.environ.get('MAIL_PASSWORD')
    alert_to = os.environ.get('ALERT_TO')
    
    if not mail_user or not mail_pass or not alert_to:
        print("⚠️ 未設定 Gmail 密鑰，略過電郵通知。")
        return

    try:
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = Header(mail_user, 'utf-8')
        message['To'] = Header(alert_to, 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_user, [alert_to], message.as_string())
        server.quit()
        print("📧 即時電郵通知已成功發送！")
    except Exception as e:
        print(f"⚠️ 發送電郵失敗: {e}")

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"cash": INITIAL_CASH, "total_equity": INITIAL_CASH, "positions": [], "history": [], "pending_orders": []}

def save_portfolio(pf):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(pf, f, ensure_ascii=False, indent=4)

def main():
    pf = load_portfolio()
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    all_tickers = list(set([p["ticker"] for p in pf["positions"]] + [o["ticker"] for o in pf["pending_orders"]]))
    market_data = {}
    
    if all_tickers:
        try:
            data = yf.download(all_tickers, period="2d", group_by="ticker", threads=True)
            for ticker in all_tickers:
                hist = data if len(all_tickers) == 1 else data[ticker]
                if not hist.empty:
                    market_data[ticker] = {
                        "open": float(hist['Open'].iloc[-1]),
                        "high": float(hist['High'].iloc[-1]),
                        "low": float(hist['Low'].iloc[-1]),
                        "close": float(hist['Close'].iloc[-1])
                    }
        except Exception as e:
            print(f"⚠️ 抓取行情錯誤: {e}")

    # 1. 檢查掛單是否成交
    new_pending = []
    newly_bought = []
    
    for order in pf["pending_orders"]:
        ticker = order["ticker"]
        if ticker not in market_data:
            new_pending.append(order)
            continue
            
        today_mkt = market_data[ticker]
        buy_price = 0
        
        if order["order_type"] == "⚠️ 條件突破單 (勿現價買)":
            if today_mkt["high"] >= order["entry"]:
                buy_price = today_mkt["open"] if today_mkt["open"] > order["entry"] else order["entry"]
        else: # 現價低吸或回調單
            if today_mkt["low"] <= order["entry"]:
                buy_price = order["entry"]

        if buy_price > 0:
            cost = buy_price * order["shares"]
            if pf["cash"] >= cost:
                pf["cash"] -= cost
                position = {
                    "ticker": ticker,
                    "buy_price": round(buy_price, 2),
                    "shares": order["shares"],
                    "stop": order["stop"],
                    "target_3r": order["target_3r"],
                    "buy_date": today_str,
                    "current_price": round(today_mkt["close"], 2),
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_percent": 0.0
                }
                pf["positions"].append(position)
                newly_bought.append(f"股票: {ticker} | 買入價: ${buy_price:.2f} | 股數: {order['shares']}")
                print(f"[{ticker}] 實時成交！買入於 ${buy_price:.2f}")
            else:
                print(f"[{ticker}] 現金不足，取消掛單。")
        else:
            new_pending.append(order)
            
    pf["pending_orders"] = new_pending

    # 如果有新成交，立刻發送 Gmail 通知
    if newly_bought:
        subject = "🚨 【AI 模擬交易實時通知】成功建立新倉位！"
        content = f"系統於 {today_str} 偵測到以下股票達到買入點並已自動模擬建倉：\n\n" + "\n".join(newly_bought)
        send_email_alert(subject, content)

    # 2. 獲取最新選股並建立掛單
    if os.path.exists(STOCKS_FILE):
        try:
            with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
                stocks_data = json.load(f).get("stocks", [])
        except:
            stocks_data = []
            
        held_and_pending_tickers = [p["ticker"] for p in pf["positions"]] + [o["ticker"] for o in pf["pending_orders"]]
        pf["pending_orders"] = [] 
        
        for s in stocks_data:
            if s["ticker"] in held_and_pending_tickers: continue
                
            position_size = pf["total_equity"] * POSITION_LIMIT
            if pf["cash"] >= position_size:
                shares = int(position_size // s["entry"])
                if shares > 0:
                    pf["pending_orders"].append({
                        "ticker": s["ticker"],
                        "order_type": s["order_type"],
                        "entry": s["entry"],
                        "stop": s["stop"],
                        "target_3r": s["target_3r"],
                        "shares": shares,
                        "date_created": today_str
                    })

    # 3. 計算總淨值
    stock_value = sum(p["current_price"] * p["shares"] for p in pf["positions"])
    pf["total_equity"] = round(pf["cash"] + stock_value, 2)
    pf["cash"] = round(pf["cash"], 2)
    
    save_portfolio(pf)
    print(f"✅ 實時監控結算完成。總淨值: ${pf['total_equity']}")

if __name__ == "__main__":
    main()
