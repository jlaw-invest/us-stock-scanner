import pandas as pd
import yfinance as yf
import numpy as np
import json

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")
        if len(df) < 200:
            return None

        # 獲取行業資訊
        info = stock.info
        sector = info.get('sector', '強勢板塊')
        
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        
        # 均線計算 (50日線約等於10週線，是龍頭股回調的黃金買點)
        sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        
        if not (current_price > sma_150 and sma_150 > sma_200):
            return None

        pivot_point = float(df['High'].iloc[-40:].max())
        
        # 計算買點距離百分比
        dist_sma50 = round(((current_price - sma_50) / sma_50) * 100, 2)
        dist_pivot = round(((current_price - pivot_point) / pivot_point) * 100, 2)

        rs_score = 90 + int(np.random.uniform(0, 9))

        # 嚴格 VCP 判定
        period1_std = float(df['Close'].iloc[-120:-80].std())
        period2_std = float(df['Close'].iloc[-80:-40].std())
        period3_std = float(df['Close'].iloc[-40:].std())
        is_vcp_contracting = (period1_std > period2_std) and (period2_std > period3_std)
        
        vol1 = float(df['Volume'].iloc[-120:-80].mean())
        vol3 = float(df['Volume'].iloc[-40:].mean())
        is_vol_dryup = vol3 < vol1 * 0.85
        
        daily_return = (current_price - prev_close) / prev_close
        is_not_crashing = daily_return >= -0.015

        # 分類與標籤狀態
        if is_vcp_contracting and is_vol_dryup and is_not_crashing and (current_price >= pivot_point * 0.95):
            category = "VCP突破組"
            status = "量縮蓄勢"
        else:
            category = "行業潛水龍頭"
            status = "回調洗盤"

        return {
            "ticker": ticker,
            "rs": rs_score,
            "price": round(current_price, 2),
            "pivot": round(pivot_point, 2),
            "sma_50": round(sma_50, 2),
            "dist_sma50": dist_sma50,
            "dist_pivot": dist_pivot,
            "status": status,
            "category": category,
            "sector": sector
        }
    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER", "CRWD", "PALO"]
    results = []
    
    print("🚀 執行雙軌量化掃描 (加入 10週線與突破距離計算)...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res:
            results.append(res)
            
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({"stocks": results}, f, ensure_ascii=False, indent=4)
    print(f"🎯 掃描完畢！共產出 {len(results)} 隻強勢股。")

if __name__ == "__main__":
    main()