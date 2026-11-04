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
        
        # 條件：淨利潤必須為正數
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
        
        # 濾網一：基本 Stage 2 上升趨勢
        if not (current_close > sma_150 and sma_150 > sma_200): return None
        rs_score = 90 + int(np.random.uniform(0, 9)) # 模擬 RS>90
        
        # 是否屬於「長青強勢股庫」(股價 > 10MA > 20MA > 50MA)
        is_long_term_strong = (current_close > sma_10) and (sma_10 > sma_20) and (sma_20 > sma_50)
        
        # ==========================================
        # 建立共用基本資料包 (包含長青庫專屬的預設狙擊計劃)
        # ==========================================
        default_entry = round(current_high + 0.05, 2)
        default_stop = round(sma_50, 2) # 長青庫預設以 50MA 防守
        default_risk = default_entry - default_stop
        
        # 確保止蝕空間合理，防守位最少預留 5%
        if default_risk <= 0 or (default_risk / default_entry) < 0.05: 
            default_stop = round(default_entry * 0.95, 2)
            default_risk = default_entry - default_stop

        base_data = {
            "ticker": ticker, "rs": rs_score, "price": round(current_close, 2),
            "sector": sector, "summary": summary,
            "net_income": net_income, "rev_growth": format_percent(info.get('revenueGrowth')),
            "roe": format_percent(info.get('returnOnEquity')),
            "sma_10": round(sma_10, 2), "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2),
            # 加入長青庫的預設狙擊手參數
            "entry": default_entry,
            "stop": default_stop,
            "risk": round(default_risk, 2),
            "target_3r": round(default_entry + (default_risk * 3), 2),
            "target_4r": round(default_entry + (default_risk * 4), 2),
            "target_5r": round(default_entry + (default_risk * 5), 2),
            "order_type": "📈 趨勢突破單",
            "reason": "強勢股順勢操作，等待突破近日高位進場。",
            "action_plan": "1. 突破信號燭高位買入。\n2. 跌破 50MA 或預設防守位即走。"
        }

        # ==========================================
        # 1. J Law 回踩均線狙擊條件 (覆蓋預設計劃)
        # ==========================================
        sniper_data = None
        dist_sma50 = round(((current_close - sma_50) / sma_50) * 100, 2)
        candle_range = current_high - current_low if (current_high - current_low) > 0 else 0.001
        close_percentile = (current_close - current_low) / candle_range
        is_strong_close = close_percentile >= 0.5 
        
        if (dist_sma50 > 8.0 and current_low <= sma_20 * 1.02 and is_strong_close) or (abs(dist_sma50) <= 4.0 and is_strong_close):
            sniper_data = base_data.copy()
            
            # MA 狙擊專用買賣點
            new_entry = round(current_high + 0.05, 2)
            new_stop = round(current_low * 0.98, 2) # MA 狙擊止蝕較緊
            new_risk = new_entry - new_stop
            
            if new_risk <= 0 or (new_risk / new_entry) < 0.02: 
                new_stop = round(new_entry * 0.95, 2)
                new_risk = new_entry - new_stop
                
            cat_name = "行業潛水龍頭 (回調 20MA)" if dist_sma50 > 8.0 else "行業潛水龍頭 (回踩 50MA)"
            
            sniper_data.update({
                "category": cat_name,
                "order_type": "⏳ F.T. 條件單",
                "entry": new_entry,
                "stop": new_stop,
                "risk": round(new_risk, 2),
                "target_3r": round(new_entry + (new_risk * 3), 2),
                "target_4r": round(new_entry + (new_risk * 4), 2),
                "target_5r": round(new_entry + (new_risk * 5), 2),
                "reason": f"{cat_name.split('(')[1].split(')')[0]} 獲支持，等待突破信號燭高位。",
                "action_plan": "1. 設置 Stop Order。\n2. 跌穿止蝕即走。"
            })

        # ==========================================
        # 2. VCP 日線波幅收縮形態偵測 + 3R/4R/5R 計劃
        # ==========================================
        vcp_data = None
        recent_40d = df.tail(40)
        
        if len(recent_40d) == 40:
            left_side_high = recent_40d['High'].iloc[:20].max()
            left_side_low = recent_40d['Low'].iloc[:20].min()
            left_volatility = (left_side_high - left_side_low) / left_side_low
            
            right_side_high = recent_40d['High'].iloc[20:].max()
            right_side_low = recent_40d['Low'].iloc[20:].min()
            right_volatility = (right_side_high - right_side_low) / right_side_low
            
            vol_5d_avg = df['Volume'].tail(5).mean()
            vol_50d_avg = df['Volume'].tail(50).mean()
            is_volume_dry = vol_5d_avg < (vol_50d_avg * 0.8)
            
            if right_volatility > 0 and right_volatility < left_volatility * 0.6 and is_volume_dry:
                pivot_point = right_side_high
                vcp_stop = right_side_low * 0.99 
                
                if current_close >= pivot_point * 0.97 and current_close <= pivot_point * 1.02:
                    vcp_entry = round(pivot_point + 0.05, 2)
                    vcp_risk = vcp_entry - vcp_stop
                    
                    if (vcp_risk / vcp_entry) < 0.02:
                        vcp_stop = vcp_entry * 0.96
                        vcp_risk = vcp_entry - vcp_stop
                        
                    vcp_data = base_data.copy()
                    vcp_data.update({
                        "category": "💎 VCP 極限收縮 (Pivot 突破)",
                        "order_type": "🎯 樞紐點條件單",
                        "entry": vcp_entry,
                        "stop": round(vcp_stop, 2),
                        "risk": round(vcp_risk, 2),
                        "target_3r": round(vcp_entry + (vcp_risk * 3), 2),
                        "target_4r": round(vcp_entry + (vcp_risk * 4), 2),
                        "target_5r": round(vcp_entry + (vcp_risk * 5), 2),
                        "reason": "日線呈現 VCP 波幅收窄及極度量縮，準備突破樞紐點。",
                        "action_plan": "1. 突破樞紐點買入。\n2. 跌破右側低點嚴格止蝕。"
                    })

        return {
            "ticker": ticker, 
            "is_strong": is_long_term_strong, 
            "base_data": base_data, 
            "sniper_data": sniper_data,
            "vcp_data": vcp_data
        }

    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER", "CRWD", "PALO"]
    strong_database = []
    sniper_list = []
    vcp_list = [] 
    
    print("🚀 執行三軌掃描：強勢資料庫 + 均線狙擊 + VCP 形態...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res:
            if res["is_strong"]: strong_database.append(res["base_data"])
            if res["sniper_data"]: sniper_list.append(res["sniper_data"])
            if res["vcp_data"]: vcp_list.append(res["vcp_data"])
            
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "database": strong_database, 
            "stocks": sniper_list,
            "vcp_stocks": vcp_list
        }, f, ensure_ascii=False, indent=4)
        
    print(f"🎯 掃描完畢！強勢庫: {len(strong_database)} 隻 | 均線狙擊: {len(sniper_list)} 隻 | VCP 形態: {len(vcp_list)} 隻")

if __name__ == "__main__":
    main()
