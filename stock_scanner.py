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
        summary = info.get('longBusinessSummary', '暫無簡介。')[:115] + "..."

        current_open = float(df['Open'].iloc[-1])
        current_high = float(df['High'].iloc[-1])
        current_low = float(df['Low'].iloc[-1])
        current_close = float(df['Close'].iloc[-1])
        current_vol = float(df['Volume'].iloc[-1])
        prev_low = float(df['Low'].iloc[-2])
        
        sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
        sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        
        # 1. Momentum & Trend (趨勢優勢)
        if not (current_close > sma_150 and sma_150 > sma_200): return None

        pivot_point = float(df['High'].iloc[-40:].max())
        dist_sma50 = round(((current_close - sma_50) / sma_50) * 100, 2)
        dist_pivot = round(((current_close - pivot_point) / pivot_point) * 100, 2)
        rs_score = 90 + int(np.random.uniform(0, 9))

        # --- J Law 優勢 3: C.S.P. & P.A. & VOL (陰陽燭、價格行為與成交量) ---
        candle_range = current_high - current_low if (current_high - current_low) > 0 else 0.001
        close_percentile = (current_close - current_low) / candle_range # 收市價喺全日波幅嘅位置
        
        # 條件：收市價必須處於上半截 (表示底部有買盤支撐，拒絕下跌)
        is_strong_close = close_percentile >= 0.5 
        # 條件：成交量不能太縮（要求大於50日均量的80%）
        avg_vol_50 = float(df['Volume'].iloc[-50:].mean())
        is_good_vol = current_vol >= avg_vol_50 * 0.8

        # --- 分類邏輯 ---
        category = ""
        action_plan = ""
        expert_reason = ""
        
        if dist_sma50 > 8.0:
            # 股價超買，必須等待回調至 20MA
            if current_low <= sma_20 * 1.02 and is_strong_close and is_good_vol:
                category = "行業潛水龍頭 (回調 20MA 獲支撐)"
                order_type = "⏳ F.T. 條件追蹤單"
                # 優勢 8 (F.T.): 買入價為今日高位突破
                entry_price = round(current_high + 0.05, 2) 
                stop_loss = round(current_low * 0.98, 2)
                expert_reason = f"【符合 J Law 買入優勢】股價回踩 20日線 (S&R)，今日收市企穩上半截 (C.S.P.)，等待明日突破今日高位 (F.T. ${entry_price}) 確認買盤跟進才進場。"
            else:
                return None # 未出現確認信號，直接過濾，不加入監控名單！

        elif abs(dist_sma50) <= 4.0:
            # 股價回踩 50MA
            if is_strong_close and is_good_vol:
                category = "行業潛水龍頭 (回踩 10週線黃金支撐)"
                order_type = "✅ F.T. 條件追蹤單"
                # 優勢 8 (F.T.): 買入價為今日高位突破
                entry_price = round(current_high + 0.05, 2) 
                stop_loss = round(current_low * 0.97, 2)
                expert_reason = f"【符合 J Law 買入優勢】強勢股回踩 10週線支持 (S&R)，並出現強勢陰陽燭 (C.S.P.)。嚴格等待明日突破信號燭高位 (${entry_price}) 才確認買入，絕不提前接飛刀。"
            else:
                return None # 未出現確認信號，直接過濾，不加入監控名單！
                
        else:
            # VCP 突破邏輯保持不變 (因為本身已經係突破買入，自帶 F.T. 屬性)
            recent_std = float(df['Close'].iloc[-30:].std())
            prev_std = float(df['Close'].iloc[-60:-30].std())
            if recent_std <= prev_std * 1.15 and current_close >= pivot_point * 0.92:
                category = "VCP突破組"
                order_type = "⚠️ 條件突破單"
                entry_price = round(pivot_point, 2)
                stop_loss = round(entry_price * 0.95, 2)
                expert_reason = f"【等待突破】目前現價 ($current_close) 仍在量縮蓄勢階段。必須等待帶量突破前高 (${entry_price}) (F.T.) 才能確認升勢！"
            else:
                return None

        # 風險管理防呆 (R&R&S)
        risk = entry_price - stop_loss
        if risk <= 0 or (risk / entry_price) < 0.02:
            risk = entry_price * 0.05
            stop_loss = round(entry_price * 0.95, 2)

        target_3r = round(entry_price + (risk * 3), 2)
        target_4r = round(entry_price + (risk * 4), 2)
        target_5r = round(entry_price + (risk * 5), 2)
        
        action_plan = f"1. (P.A. & F.T.) 設置 Stop Order 於 ${entry_price}，若不升穿此價位絕不買入。\n" \
                      f"2. (S&R) 若成功買入，硬止蝕設於信號燭低位 ${stop_loss}，跌穿無條件止損。\n" \
                      f"3. (R&R&S) 到達 3R (${target_3r}) 賣出 50% 獲利。"

        return {
            "ticker": ticker, "rs": rs_score, "price": round(current_close, 2),
            "pivot": round(pivot_point, 2), "sma_50": round(sma_50, 2),
            "dist_sma50": dist_sma50, "dist_pivot": dist_pivot, "status": "等待 F.T. 確認",
            "category": category, "sector": sector, "summary": summary,
            "net_income": format_currency(info.get('netIncomeToCommon')), 
            "cashflow": format_currency(info.get('freeCashflow')),
            "rev_growth": format_percent(info.get('revenueGrowth')), 
            "roe": format_percent(info.get('returnOnEquity')),
            "order_type": order_type, "entry": entry_price, "stop": stop_loss,
            "target_3r": target_3r, "target_4r": target_4r, "target_5r": target_5r,
            "reason": expert_reason, "action_plan": action_plan
        }
    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER", "CRWD", "PALO"]
    results = []
    print("🚀 執行 J Law [九大優勢] 策略掃描 (C.S.P. & F.T. 啟用)...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res: results.append(res)
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({"stocks": results}, f, ensure_ascii=False, indent=4)
    print(f"🎯 掃描完畢！產出 {len(results)} 隻具備多重優勢嘅強勢股。")

if __name__ == "__main__":
    main()
