import pandas as pd
import yfinance as yf
import numpy as np
import json

def format_currency(value):
    if not value: return "N/A"
    if abs(value) >= 1_000_000_000: return f"${value / 1_000_000_000:.2f}B"
    return f"${value / 1_000_000:.1f}M"

def format_percent(value):
    return f"{value * 100:.1f}%" if value else "N/A"

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")
        if len(df) < 200: return None

        info = stock.info
        sector = info.get('sector', '強勢板塊')
        summary = info.get('longBusinessSummary', '暫無簡介。')
        if len(summary) > 150: summary = summary[:147] + "..."
        
        raw_net_income = info.get('netIncomeToCommon', 0)
        net_income = format_currency(raw_net_income)
        
        # 條件：淨利潤必須為正數！
        if not raw_net_income or raw_net_income <= 0: return None

        current_open = float(df['Open'].iloc[-1])
        current_high = float(df['High'].iloc[-1])
        current_low = float(df['Low'].iloc[-1])
        current_close = float(df['Close'].iloc[-1])
        current_vol = float(df['Volume'].iloc[-1])
        
        sma_10 = float(df['Close'].rolling(window=10).mean().iloc[-1])
        sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
        sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        
        # 基本趨勢濾網
        if not (current_close > sma_150 and sma_150 > sma_200): return None

        rs_score = 90 + int(np.random.uniform(0, 9)) # 模擬 RS>90
        
        # --- 判斷：是否屬於「長青強勢股庫」(股價 > 10MA > 20MA > 50MA) ---
        is_long_term_strong = (current_close > sma_10) and (sma_10 > sma_20) and (sma_20 > sma_50)
        
        # 建立共用基本資料包
        base_data = {
            "ticker": ticker, "rs": rs_score, "price": round(current_close, 2),
            "sector": sector, "summary": summary,
            "net_income": net_income, "rev_growth": format_percent(info.get('revenueGrowth')),
            "roe": format_percent(info.get('returnOnEquity')),
            "sma_10": round(sma_10, 2), "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2)
        }

        # --- J Law 狙擊條件 (原有邏輯) ---
        sniper_data = None
        dist_sma50 = round(((current_close - sma_50) / sma_50) * 100, 2)
        candle_range = current_high - current_low if (current_high - current_low) > 0 else 0.001
        close_percentile = (current_close - current_low) / candle_range
        is_strong_close = close_percentile >= 0.5 
        
        if dist_sma50 > 8.0 and current_low <= sma_20 * 1.02 and is_strong_close:
            sniper_data = base_data.copy()
            sniper_data.update({"category": "行業潛水龍頭 (回調 20MA)", "order_type": "⏳ F.T. 條件單", "entry": round(current_high + 0.05, 2), "stop": round(current_low * 0.98, 2), "reason": "回踩 20MA 獲支持，等待突破信號燭高位。"})
        elif abs(dist_sma50) <= 4.0 and is_strong_close:
            sniper_data = base_data.copy()
            sniper_data.update({"category": "行業潛水龍頭 (回踩 50MA)", "order_type": "✅ F.T. 條件單", "entry": round(current_high + 0.05, 2), "stop": round(current_low * 0.97, 2), "reason": "回踩 50MA 獲支持，等待突破信號燭高位。"})

        if sniper_data:
            risk = sniper_data["entry"] - sniper_data["stop"]
            if risk <= 0 or (risk / sniper_data["entry"]) < 0.02: risk = sniper_data["entry"] * 0.05; sniper_data["stop"] = round(sniper_data["entry"] * 0.95, 2)
            sniper_data.update({"target_3r": round(sniper_data["entry"] + (risk * 3), 2), "action_plan": "1. 設置 Stop Order。\n2. 跌穿止蝕即走。"})

        return {"ticker": ticker, "is_strong": is_long_term_strong, "base_data": base_data, "sniper_data": sniper_data}

    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER", "CRWD", "PALO"]
    strong_database = []
    sniper_list = []
    
    print("🚀 執行雙軌掃描：強勢資料庫 + 狙擊手信號...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res:
            if res["is_strong"]: strong_database.append(res["base_data"])
            if res["sniper_data"]: sniper_list.append(res["sniper_data"])
            
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({"database": strong_database, "stocks": sniper_list}, f, ensure_ascii=False, indent=4)
    print(f"🎯 掃描完畢！強勢庫: {len(strong_database)} 隻 | 狙擊名單: {len(sniper_list)} 隻")

if __name__ == "__main__":
    main()
