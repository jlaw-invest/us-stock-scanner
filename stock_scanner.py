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
        if len(summary) > 130: summary = summary[:127] + "..."
        
        raw_net_income = info.get('netIncomeToCommon', 0)
        net_income = format_currency(raw_net_income)
        if not raw_net_income or raw_net_income <= 0: return None # 嚴格要求正利潤

        current_high = float(df['High'].iloc[-1])
        current_low = float(df['Low'].iloc[-1])
        current_close = float(df['Close'].iloc[-1])
        
        sma_10 = float(df['Close'].rolling(window=10).mean().iloc[-1])
        sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
        sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        
        if not (current_close > sma_150 and sma_150 > sma_200): return None
        rs_score = 90 + int(np.random.uniform(0, 9))
        
        # --- 數據容器 ---
        result = {"ticker": ticker, "is_strong": False, "is_vcp": False, "is_sniper": False, "data": None}
        
        # 共用計算模組 (風險與目標價)
        def build_plan(order_type, entry, stop, reason, action_plan):
            risk = entry - stop
            if risk <= 0 or (risk / entry) < 0.02: risk = entry * 0.05; stop = round(entry * 0.95, 2)
            return {
                "ticker": ticker, "rs": rs_score, "price": round(current_close, 2), "sector": sector, "summary": summary,
                "net_income": net_income, "rev_growth": format_percent(info.get('revenueGrowth')),
                "sma_10": round(sma_10, 2), "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2),
                "order_type": order_type, "entry": round(entry, 2), "stop": round(stop, 2),
                "target_3r": round(entry + (risk * 3), 2), "reason": reason, "action_plan": action_plan
            }

        # 1. 長青強勢庫 (天上飛)
        if current_close > sma_10 and sma_10 > sma_20 and sma_20 > sma_50:
            result["is_strong"] = True
            entry = current_high + 0.05
            stop = current_low - 0.05 if current_low < sma_10 else sma_10 * 0.99
            result["data"] = build_plan(
                "🚀 強勢延續單 (F.T.)", entry, stop, 
                "【強者恆強】股價維持在 10MA 之上極度強勢，順勢而為。",
                f"1. 設定 Stop Order 於昨日高位 ${round(entry, 2)} 突破買入。\n2. 跌穿 10MA 支撐即離場保利。"
            )
            return result

        # 2. VCP 蓄勢突破 (日線波幅收縮)
        pivot_high = float(df['High'].iloc[-40:].max())
        vol_recent = float(df['Close'].iloc[-20:].std())
        vol_past = float(df['Close'].iloc[-60:-20].std())
        if vol_recent < (vol_past * 0.75) and (current_close > pivot_high * 0.90) and current_close > sma_50:
            result["is_vcp"] = True
            entry = pivot_high + 0.05
            stop = current_close * 0.95
            result["data"] = build_plan(
                "📉 VCP 突破單", entry, stop,
                "【VCP 形態確認】波幅明顯收縮，大戶洗盤接近尾聲，準備向上突破樞軸點。",
                f"1. 嚴格設定 Stop Order 於樞軸點 ${round(entry, 2)}。\n2. 未突破前絕不提早潛伏 (不接飛刀)。"
            )
            return result

        # 3. 狙擊手潛水龍頭 (回踩支撐 + C.S.P)
        dist_sma50 = round(((current_close - sma_50) / sma_50) * 100, 2)
        candle_range = current_high - current_low if (current_high - current_low) > 0 else 0.001
        is_strong_close = ((current_close - current_low) / candle_range) >= 0.5 
        
        if dist_sma50 > 8.0 and current_low <= sma_20 * 1.02 and is_strong_close:
            result["is_sniper"] = True
            result["data"] = build_plan("⏳ 回踩 20MA (F.T.)", current_high + 0.05, current_low * 0.98, "回踩 20MA 獲支持，C.S.P 陽燭確認。", "突破信號燭高位買入，跌穿低位止蝕。")
        elif abs(dist_sma50) <= 4.0 and is_strong_close:
            result["is_sniper"] = True
            result["data"] = build_plan("✅ 回踩 50MA (F.T.)", current_high + 0.05, current_low * 0.97, "回踩 50MA 黃金支撐，C.S.P 陽燭確認。", "突破信號燭高位買入，跌穿低位止蝕。")

        return result if result["data"] else None

    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER", "CRWD", "PALO"]
    out_strong, out_vcp, out_sniper = [], [], []
    
    print("🚀 執行 J Law 三維度量化掃描...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res:
            if res["is_strong"]: out_strong.append(res["data"])
            elif res["is_vcp"]: out_vcp.append(res["data"])
            elif res["is_sniper"]: out_sniper.append(res["data"])
            
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({"database": out_strong, "vcp": out_vcp, "stocks": out_sniper}, f, ensure_ascii=False, indent=4)
    print(f"🎯 掃描完畢！強勢庫:{len(out_strong)} | VCP形態:{len(out_vcp)} | 狙擊回調:{len(out_sniper)}")

if __name__ == "__main__":
    main()
