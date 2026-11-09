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
POSITION_LIMIT = 0.20 # 每隻股票最多佔總資金 20%

def send_email_alert(subject, content):
    mail_user = os.environ.get('MAIL_USER')
    mail_pass = os.environ.get('MAIL_PASSWORD')
    alert_to = os.environ.get('ALERT_TO')
    if not mail_user or not mail_pass or not alert_to: return
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = Header(mail_user, 'utf-8')
        msg['To'] = Header(alert_to, 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(mail_user, mail_pass)
        server.sendmail(mail_user, [alert_to], msg.as_string())
        server.quit()
    except Exception as e:
        print(f"發信失敗: {e}")

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
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
            print(f"抓取行情錯誤: {e}")

    sold_alerts = []
    newly_bought = []
    
    active_positions = []
    for p in pf["positions"]:
        ticker = p["ticker"]
        if ticker in market_data:
            today_mkt = market_data[ticker]
            latest_close = today_mkt["close"]
            
            p["current_price"] = round(latest_close, 2)
            p["unrealized_pnl"] = round((latest_close - p["buy_price"]) * p["shares"], 2)
            p["unrealized_pnl_percent"] = round((latest_close - p["buy_price"]) / p["buy_price"] * 100, 2)
            
            # 止蝕判斷
            if today_mkt["low"] <= p["stop"]:
                sell_price = p["stop"] if today_mkt["open"] > p["stop"] else today_mkt["open"]
                pnl = round((sell_price - p["buy_price"]) * p["shares"], 2)
                pf["cash"] += (sell_price * p["shares"])
                pf["history"].append({
                    "ticker": ticker, "buy_date": p["buy_date"], "sell_date": today_str,
                    "buy_price": p["buy_price"], "sell_price": round(sell_price, 2),
                    "pnl": pnl, "pnl_percent": round((sell_price - p["buy_price"]) / p["buy_price"] * 100, 2),
                    "reason": "🔴 跌穿支持，觸發硬止蝕"
                })
                # 🔥 這裡修復了 f-string 錯誤 🔥
                sold_alerts.append(f"🔴 [{ticker}] 觸發止蝕賣出！價格: ${sell_price:.2f} | 盈虧: ${pnl:.2f}")
                continue
                
            # 止賺判斷
            elif today_mkt["high"] >= p.get("target_3r", 99999):
                sell_price = p["target_3r"] if today_mkt["open"] < p["target_3r"] else today_mkt["open"]
                pnl = round((sell_price - p["buy_price"]) * p["shares"], 2)
                pf["cash"] += (sell_price * p["shares"])
                pf["history"].append({
                    "ticker": ticker, "buy_date": p["buy_date"], "sell_date": today_str,
                    "buy_price": p["buy_price"], "sell_price": round(sell_price, 2),
                    "pnl": pnl, "pnl_percent": round((sell_price - p["buy_price"]) / p["buy_price"] * 100, 2),
                    "reason": "🟢 達到 3R 目標自動獲利"
                })
                # 🔥 這裡修復了 f-string 錯誤 🔥
                sold_alerts.append(f"🟢 [{ticker}] 達到 3R 目標獲利賣出！價格: ${sell_price:.2f} | 盈虧: ${pnl:.2f}")
                continue

        active_positions.append(p)
    pf["positions"] = active_positions

    new_pending = []
    for order in pf["pending_orders"]:
        ticker = order["ticker"]
        if ticker not in market_data:
            new_pending.append(order)
            continue
            
        today_mkt = market_data[ticker]
        buy_price = 0
        
        if today_mkt["high"] >= order["entry"]:
            buy_price = today_mkt["open"] if today_mkt["open"] > order["entry"] else order["entry"]

        if buy_price > 0:
            cost = buy_price * order["shares"]
            if pf["cash"] >= cost:
                pf["cash"] -= cost
                position = {
                    "ticker": ticker, "buy_price": round(buy_price, 2), "shares": order["shares"],
                    "stop": order["stop"], "target_3r": order.get("target_3r", buy_price*1.2),
                    "buy_date": today_str, "current_price": round(today_mkt["close"], 2),
                    "unrealized_pnl": round((today_mkt["close"] - buy_price) * order["shares"], 2),
                    "unrealized_pnl_percent": round((today_mkt["close"] - buy_price) / buy_price * 100, 2)
                }
                pf["positions"].append(position)
                newly_bought.append(f"🟢 [{ticker}] F.T. 突破買入！價格: ${buy_price:.2f} | 股數: {order['shares']}")
            else:
                new_pending.append(order)
        else:
            if today_mkt["close"] < order["stop"]:
                pass 
            else:
                new_pending.append(order)
    pf["pending_orders"] = new_pending

    alerts_text = newly_bought + sold_alerts
    if alerts_text:
        send_email_alert("🚨 【AI 模擬交易】倉位異動！", "系統執行了以下交易：\n\n" + "\n".join(alerts_text))

    if os.path.exists(STOCKS_FILE):
        try:
            with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
                sd = json.load(f)
                new_signals = sd.get("database", []) + sd.get("vcp", []) + sd.get("stocks", [])
        except:
            new_signals = []
            
        held_and_pending = [p["ticker"] for p in pf["positions"]] + [o["ticker"] for o in pf["pending_orders"]]
        
        for s in new_signals:
            if s["ticker"] in held_and_pending: continue
            
            if "order_type" in s and s.get("entry"):
                position_size = pf["total_equity"] * POSITION_LIMIT
                if pf["cash"] >= position_size:
                    shares = int(position_size // s["entry"])
                    if shares > 0:
                        pf["pending_orders"].append({
                            "ticker": s["ticker"], "order_type": s["order_type"], "entry": s["entry"],
                            "stop": s["stop"], "target_3r": s["target_3r"], "shares": shares, "date_created": today_str
                        })

    stock_value = sum(p["current_price"] * p["shares"] for p in pf["positions"])
    pf["total_equity"] = round(pf["cash"] + stock_value, 2)
    pf["cash"] = round(pf["cash"], 2)
    
    save_portfolio(pf)

if __name__ == "__main__":
    main()
