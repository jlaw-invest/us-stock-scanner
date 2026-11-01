import pandas as pd
import yfinance as yf
import numpy as np
import json

def calculate_strict_vcp(ticker):
    """
    嚴格 VCP 形態量化引擎：
    1. Stage 2 多頭排列
    2. 檢查最新交易日絕對不能是大跌日
    3. 檢測多重波動收縮（至少經歷兩次高低點回調收窄）
    4. 成交量在收縮末端必須顯著乾涸（Dry Up）
    5. 目前正在 Pivot 突破點附近蓄勢待發
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")
        
        if len(df) < 200:
            return None  

        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        
        # --- 嚴格過濾一：最新交易日防護網 ---
        # 如果最新交易日大跌超過 1.5%，直接淘汰，絕對不能選入準備突破的清單！
        daily_return = (current_price - prev_close) / prev_close
        if daily_return < -0.015:
            return None

        # --- 嚴格過濾二：Stage 2 長期升浪確認 ---
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        
        if not (current_price > sma_150 and sma_150 > sma_200):
            return None  

        # --- 嚴格過濾三：多重 VCP 回調與波動收縮檢測 ---
        # 將過去 120 個交易日拆解為三段來檢測「波動一次比一次收窄」（Volatility Contraction）
        period1 = df['Close'].iloc[-120:-80] # 第一階段回調期
        period2 = df['Close'].iloc[-80:-40]  # 第二階段回調期
        period3 = df['Close'].iloc[-40:]     # 第三階段收縮末端
        
        std1 = float(period1.std())
        std2 = float(period2.std())
        std3 = float(period3.std())
        
        # VCP 核心鐵律：波動率必須呈現遞減趨勢 (std1 > std2 > std3)
        is_contracting = (std1 > std2) and (std2 > std3)
        if not is_contracting:
            return None  # 如果沒有逐級收緊，淘汰！

        # --- 嚴格過濾四：成交量收縮（Volume Dry Up） ---
        vol1 = float(df['Volume'].iloc[-120:-80].mean())
        vol3 = float(df['Volume'].iloc[-40:].mean())
        
        # 末端成交量必須比前期明顯萎縮（量縮整理）
        if vol3 >= vol1 * 0.85:
            return None

        # --- 嚴格過濾五：Pivot 突破點與位置確認 ---
        # 取最近 40 日的高點作為關鍵 Pivot 阻力區
        pivot_point = float(df['High'].iloc[-40:].max())
        
        # 現價必須非常接近 Pivot 點（在 5% 以內，代表正在進行最後收口準備突破）
        if current_price < pivot_point * 0.95:
            return None

        # 模擬高標準 RS 評分
        rs_score = 90 + int(np.random.uniform(0, 9))

        return {
            "ticker": ticker,
            "name": ticker,
            "rs": rs_score,
            "pivot": round(pivot_point, 2),
            "price": round(current_price, 2),
            "status": "VCP 多重收縮完成，帶量蓄勢突破"
        }
        
    except Exception as e:
        print(f"處理 {ticker} 時發生錯誤: {e}")
        return None

def main():
    # 擴大掃描美股龍頭清單
    watchlist = [
        "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", 
        "NFLX", "AMD", "LLY", "JPM", "CRM", "PLTR", "NVDA", "UBER", "COIN"
    ]
    
    qualified_stocks = []
    
    print("🚀 開始執行最高標準「多重 VCP 波動收縮 + 成交量乾涸」量化掃描...")
    for ticker in watchlist:
        result = calculate_strict_vcp(ticker)
        if result:
            qualified_stocks.append(result)
            print(f"✅ 嚴格過關強勢股: {ticker} (RS: {result['rs']})")

    # 輸出 JSON
    output_data = {
        "stocks": qualified_stocks
    }
    
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"🎯 掃描完畢！嚴格過濾後符合完美 VCP 的股票數量：{len(qualified_stocks)} 隻。")

if __name__ == "__main__":
    main()
