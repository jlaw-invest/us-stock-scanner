import json
import os
import yfinance as yf
from datetime import datetime

PORTFOLIO_FILE = 'portfolio.json'
STOCKS_FILE = 'stocks_data.json'
INITIAL_CASH = 10000.0
POSITION_LIMIT = 0.20 # 每隻股票最多佔總資金 20%
MARKET_INDEX = "^GSPC" # S&P 500 大市指標

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"cash": INITIAL_CASH, "total_equity": INITIAL_CASH, "positions": [], "history": [], "pending_orders": []}

def save_portfolio(pf):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(pf, f, ensure_ascii=False, indent=4)

def check_market_trend():
    # 檢查 S&P 500 是否高於 20日線，大市偏弱時暫停建倉
    try:
        hist = yf.Ticker(MARKET_INDEX).history(period="30d")
        if hist.empty: return True
        current_close = float(hist['Close'].iloc[-1])
        sma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
        return current_close > sma_20
    except:
        return True

def main():
    pf = load_portfolio()
    today_str = datetime.now().strftime("%Y-%m-%d")
    is_market_good = check_market_trend()
    
    market_status = "🟢 大市健康 (允許建倉)" if is_market_good else "🔴 大市轉弱 (暫停買入新股)"
    print(f"💼 啟動嚴謹版 AI 模擬交易員... | {market_status} | 目前現金: ${pf['cash']:.2f}")
    
    all_tickers = list(set([p["ticker"] for p in pf["positions"]] + [o["ticker"] for o in pf["pending_orders"]]))
    market_data = {}
    
    if all_tickers:
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

    # 1. 處理持倉平倉 (止蝕/止盈)
    new_positions = []
    for p in pf["positions"]:
        ticker = p["ticker"]
        if ticker not in market_data:
            new_positions.append(p)
            continue
            
        today_mkt = market_data[ticker]
        sell_price = 0
        reason = ""
        
        # 裂口低開檢查
        if today_mkt["open"] <= p["stop"]:
            sell_price = today_mkt["open"]
            reason = "🚨 裂口低開，被迫以開盤價止蝕"
        elif today_mkt["low"] <= p["stop"]:
            sell_price = p["stop"]
            reason = "🛑 盤中觸及止蝕"
        elif today_mkt["high"] >= p["target_3r"]:
            sell_price = p["target_3r"]
            reason = "🎯 達到 3R 目標全數獲利"
            
        if sell_price > 0:
            revenue = sell_price * p["shares"]
            pnl = revenue - (p["buy_price"] * p["shares"])
            pf["cash"] += revenue
            pf["history"].append({
                "ticker": ticker, 
                "buy_price": p["buy_price"], 
                "sell_price": round(sell_price, 2),
                "shares": p["shares"], 
                "pnl": round(pnl, 2), 
                "pnl_percent": round((sell_price / p["buy_price"] - 1) * 100, 2),
                "buy_date": p["buy_date"], 
                "sell_date": today_str, 
                "reason": reason
            })
            print(f"[{ticker}] 賣出於 ${sell_price:.2f} ({reason}) | 盈虧: ${pnl:.2f}")
        else:
            p["current_price"] = round(today_mkt["close"], 2)
            p["unrealized_pnl"] = round((today_mkt["close"] - p["buy_price"]) * p["shares"], 2)
            p["unrealized_pnl_percent"] = round((today_mkt["close"] / p["buy_price"] - 1) * 100, 2)
            new_positions.append(p)
            
    pf["positions"] = new_positions

    # 2. 檢查條件掛單是否在今天觸發成交
    new_pending = []
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
        else:
            buy_price = today_mkt["open"]

        if buy_price > 0:
            cost = buy_price * order["shares"]
            if pf["cash"] >= cost:
                pf["cash"] -= cost
                pf["positions"].append({
                    "ticker": ticker,
                    "buy_price": round(buy_price, 2),
                    "shares": order["shares"],
                    "stop": order["stop"],
                    "target_3r": order["target_3r"],
                    "buy_date": today_str,
                    "current_price": round(today_mkt["close"], 2),
                    "unrealized_pnl": round((today_mkt["close"] - buy_price) * order["shares"], 2),
                    "unrealized_pnl_percent": round((today_mkt["close"] / buy_price - 1) * 100, 2)
                })
                print(f"[{ticker}] 訂單成交！買入於 ${buy_price:.2f} ({order['shares']} 股)")
            else:
                print(f"[{ticker}] 現金不足，取消訂單。")
        else:
            new_pending.append(order)
            
    pf["pending_orders"] = new_pending

    # 3. 大市健康時，為今日選出的新股設置掛單
    if is_market_good and os.path.exists(STOCKS_FILE):
        with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
            stocks_data = json.load(f).get("stocks", [])
            
        held_and_pending_tickers = [p["ticker"] for p in pf["positions"]] + [o["ticker"] for o in pf["pending_orders"]]
        pf["pending_orders"] = [] 
        
        for s in stocks_data:
            if s["ticker"] in held_and_pending_tickers: continue
                
            position_size = pf["total_equity"] * POSITION_LIMIT
            
            if pf["cash"] >= position_size and pf["cash"] - position_size > (pf["total_equity"] * 0.05):
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
                    print(f"[{s['ticker']}] 產生新掛單：準備以 ${s['entry']} 買入 ({s['order_type']})")
    elif not is_market_good:
        print("⚠️ 大市偏弱，清空所有等待中的買入掛單，保留現金。")
        pf["pending_orders"] = []

    # 4. 結算
    stock_value = sum(p["current_price"] * p["shares"] for p in pf["positions"])
    pf["total_equity"] = round(pf["cash"] + stock_value, 2)
    pf["cash"] = round(pf["cash"], 2)
    
    save_portfolio(pf)
    print(f"✅ 結算完成。總淨值: ${pf['total_equity']}")

if __name__ == "__main__":
    main()
  
