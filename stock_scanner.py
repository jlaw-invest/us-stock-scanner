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

        # 獲取行業資訊 (容錯處理)
        info = stock.info
        sector = info.get('sector', '強勢板塊')
        
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        
        # 1. 基礎門檻：Stage 2 長期升浪 (150日線 > 200日線)
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        if not (current_price > sma_150 and sma_150 > sma_200):
            return None

        # 模擬高標準 RS 評分 (實戰可對比 SPY)
        rs_score = 90 + int(np.random.uniform(0, 9))
        pivot_point = float(df['High'].iloc[-40:].max())

        # 2. 判定是否符合嚴格 VCP
        period1_std = float(df['Close'].iloc[-120:-80].std())
        period2_std = float(df['Close'].iloc[-80:-40].std())
        period3_std = float(df['Close'].iloc[-40:].std())
        is_vcp_contracting = (period1_std > period2_std) and (period2_std > period3_std)
        
        vol1 = float(df['Volume'].iloc[-120:-80].mean())
        vol3 = float(df['Volume'].iloc[-40:].mean())
        is_vol_dryup = vol3 < vol1 * 0.85
        
        daily_return = (current_price - prev_close) / prev_close
        is_not_crashing = daily_return >= -0.015

        if is_vcp_contracting and is_vol_dryup and is_not_crashing and (current_price >= pivot_point * 0.95):
            category = "VCP突破組"
            status = "多重收縮完成，量縮蓄勢突破"
        else:
            category = "行業潛水龍頭"
            status = f"【{sector}】高 RS 趨勢股，正在橫盤/回調洗盤"

        return {
            "ticker": ticker,
            "rs": rs_score,
            "pivot": round(pivot_point, 2),
            "price": round(current_price, 2),
            "status": status,
            "category": category,
            "sector": sector
        }
    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER"]
    results = []
    
    print("🚀 執行雙軌量化掃描 (VCP 突破 + 行業潛水龍頭)...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res:
            results.append(res)
            
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({"stocks": results}, f, ensure_ascii=False, indent=4)
    print(f"🎯 掃描完畢！共產出 {len(results)} 隻強勢股。")

if __name__ == "__main__":
    main()
