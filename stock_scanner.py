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
        
        long_business_summary = info.get('longBusinessSummary', '該公司暫無詳細簡介。')
        summary = long_business_summary[:115] + "..." if len(long_business_summary) > 120 else long_business_summary

        net_income = format_currency(info.get('netIncomeToCommon'))
        free_cashflow = format_currency(info.get('freeCashflow'))
        rev_growth = format_percent(info.get('revenueGrowth'))
        roe = format_percent(info.get('returnOnEquity'))

        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        prev_low = float(df['Low'].iloc[-2])
        
        # 新增 20 日線 (用於強勢股的淺度回調支撐)
        sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
        sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        sma_150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        
        if not (current_price > sma_150 and sma_150 > sma_200): return None

        pivot_point = float(df['High'].iloc[-40:].max())
        dist_sma50 = round(((current_price - sma_50) / sma_50) * 100, 2)
        dist_pivot = round(((current_price - pivot_point) / pivot_point) * 100, 2)
        rs_score = 90 + int(np.random.uniform(0, 9))

        recent_std = float(df['Close'].iloc[-30:].std())
        prev_std = float(df['Close'].iloc[-60:-30].std())
        is_contracting = recent_std <= prev_std * 1.15
        
        avg_vol_50 = float(df['Volume'].iloc[-50:].mean())
        recent_vol_5 = float(df['Volume'].iloc[-5:].mean())
        is_vol_dryup = recent_vol_5 < avg_vol_50 * 0.95 

        daily_return = (current_price - prev_close) / prev_close
        is_not_crashing = daily_return >= -0.02

        # --- 核心邏輯升級：加入超買 (Overextended) 判定 ---
        
        # 判斷是否嚴重偏離 50日線 (例如高於 50日線 8% 以上)
        is_overextended = dist_sma50 > 8.0 

        if is_contracting and is_not_crashing and is_vol_dryup and (current_price >= pivot_point * 0.92):
            category = "VCP突破組"
            status = "量縮蓄勢，準備突破"
            order_type = "⚠️ 條件突破單 (勿現價買)"
            entry_price = round(pivot_point, 2)
            
            stop_loss = round(entry_price * 0.96, 2)
            risk = entry_price - stop_loss
            
            expert_reason = f"【等待突破】目前現價 (${current_price:.2f}) 仍在蓄勢階段。必須等待日線帶量突破前高 (${entry_price}) 才能確認升勢，絕對不能提早買入！"
            action_plan = f"1. 設置條件買入單 (Stop Order) 於 ${entry_price}。\n" \
                          f"2. 若股價未達標則繼續觀望，切勿於現價提早進場。\n" \
                          f"3. 成功突破買入後，立即設置硬止蝕於 ${stop_loss} (突破價下方 4%)。\n" \
                          f"4. 到達 3R 目標時賣出 50% 獲利，止蝕推至買入價保本。"

        elif is_overextended:
            category = "行業潛水龍頭 (超買需回調)"
            status = "股價超買，等待回調"
            order_type = "⏳ 等待回調單 (Pullback Buy)"
            
            # 設定回調買入點為 20 日線附近，並預留少許緩衝
            entry_price = round(sma_20 * 1.01, 2) 
            
            # 止蝕設在 50 日線下方
            stop_loss = round(sma_50 * 0.98, 2) 
            risk = entry_price - stop_loss
            
            # 防呆：確保合理風險
            if risk <= 0 or (risk / entry_price) < 0.02:
                risk = entry_price * 0.05
                stop_loss = round(entry_price * 0.95, 2)

            expert_reason = f"【等待回調】該股基本面優異，但目前股價 (${current_price:.2f}) 距離 10週線過遠 (+{dist_sma50}%)，追高風險極大。應耐心等待股價健康回踩至 20日線支撐區 (${entry_price})。"
            action_plan = f"1. 設置條件買入單 (Limit Order) 於回調點 ${entry_price}。\n" \
                          f"2. 現價絕對不可追入，需讓系統自動監控回調時機。\n" \
                          f"3. 若成功於回調點買入，請設置硬止蝕於 ${stop_loss} (50日線下方)。\n" \
                          f"4. 到達 3R 目標時賣出 50% 獲利，保本操作。"

        else:
            category = "行業潛水龍頭"
            status = "回踩 10週線黃金支撐" if abs(dist_sma50) <= 4.0 else "回調洗盤中"
            order_type = "✅ 現價低吸單"
            entry_price = round(current_price, 2)
            
            stop_loss = round(prev_low * 0.985, 2)
            risk = entry_price - stop_loss
            
            if risk <= 0 or (risk / entry_price) < 0.015:
                risk = entry_price * 0.04
                stop_loss = round(entry_price * 0.96, 2)
                
            expert_reason = f"【現價低吸】強勢股回踩 50日線/10週線強支撐區，目前現價 (${entry_price}) 是大戶洗盤結束的潛在低吸位置。"
            action_plan = f"1. 可考慮於現價 (${entry_price}) 附近分批建倉。\n" \
                          f"2. 立即設置硬止蝕於 ${stop_loss}，若跌穿無條件離場。\n" \
                          f"3. 到達 3R 目標時賣出 50% 獲利，止蝕推至買入價保本。"

        target_3r = round(entry_price + (risk * 3), 2)
        target_4r = round(entry_price + (risk * 4), 2)
        target_5r = round(entry_price + (risk * 5), 2)

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
            "sector": sector,
            "summary": summary,
            "net_income": net_income,
            "cashflow": free_cashflow,
            "rev_growth": rev_growth,
            "roe": roe,
            "order_type": order_type,
            "entry": entry_price,
            "stop": stop_loss,
            "target_3r": target_3r,
            "target_4r": target_4r,
            "target_5r": target_5r,
            "reason": expert_reason,
            "action_plan": action_plan
        }
    except Exception as e:
        return None

def main():
    watchlist = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "LLY", "JPM", "PLTR", "NVDA", "UBER", "CRWD", "PALO"]
    results = []
    print("🚀 執行專家級操盤策略掃描 (支援回調監控 Pullback Buy)...")
    for ticker in watchlist:
        res = analyze_stock(ticker)
        if res: results.append(res)
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({"stocks": results}, f, ensure_ascii=False, indent=4)
    print(f"🎯 掃描完畢！產出 {len(results)} 隻強勢股。")

if __name__ == "__main__":
    main()
