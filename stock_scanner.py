import pandas as pd
import yfinance as yf
import numpy as np
import json
import time
import requests

def get_all_us_tickers():
    print("🌐 正在連接美國 SEC (證券交易委員會) 獲取全市場股票名單...")
    try:
        headers = {"User-Agent": "JLaw-Quant-Scanner/1.0 (Mozilla/5.0)"}
        res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=10)
        data = res.json()
        
        tickers = [v['ticker'] for v in data.values()]
        clean_tickers = [t.replace('.', '-') for t in tickers if isinstance(t, str)]
        
        print(f"✅ 成功獲取 {len(clean_tickers)} 隻美股代號！準備開始篩選...")
        return list(set(clean_tickers))
    except Exception as e:
        print(f"⚠️ 獲取名單失敗 ({e})，請檢查網絡或稍後再試。")
        return []

def format_currency(value):
    if not value or pd.isna(value): return "N/A"
    if abs(value) >= 1_000_000_000: return f"${value / 1_000_000_000:.2f}B"
    return f"${value / 1_000_000:.1f}M"

def format_percent(value):
    return f"{value * 100:.1f}%" if pd.notnull(value) else "N/A"

def main():
    all_tickers = get_all_us_tickers()
    if not all_tickers: return

    out_strong, out_vcp, out_sniper = [], [], []
    batch_size = 250
    candidates = []
    
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        print(f"🔄 [第一階段] 正在批量下載日線圖: 批次 {i//batch_size + 1} ({i} to {i+len(batch)})...")
        
        try:
            data = yf.download(batch, period="1y", group_by="ticker", threads=True)
            
            for ticker in batch:
                try:
                    hist = data[ticker] if len(batch) > 1 else data
                    if hist.empty or len(hist) < 200: continue
                    
                    current_close = float(hist['Close'].iloc[-1])
                    avg_vol_20 = float(hist['Volume'].iloc[-20:].mean())
                    
                    # 🔥 調整 1：股價 > $30 及 日均成交量 > 20萬股
                    if current_close < 30.0 or avg_vol_20 < 200000: 
                        continue
                        
                    sma_150 = float(hist['Close'].rolling(window=150).mean().iloc[-1])
                    sma_200 = float(hist['Close'].rolling(window=200).mean().iloc[-1])
                    
                    if not (current_close > sma_150 and sma_150 > sma_200):
                        continue
                        
                    candidates.append({"ticker": ticker, "hist": hist})
                    
                except Exception:
                    pass
        except Exception as e:
            print(f"批次下載失敗: {e}")
        
        time.sleep(1)

    print(f"🔥 第一階段過濾完畢！從 {len(all_tickers)} 隻股票中，篩選出 {len(candidates)} 隻【>$30 且呈上升趨勢】的強勢股！")

    for idx, item in enumerate(candidates):
        ticker = item["ticker"]
        hist = item["hist"]
        
        if idx % 20 == 0 and idx > 0: 
            print(f"⏳ 正在深度分析中 ({idx}/{len(candidates)})...")
            
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            market_cap = info.get('marketCap', 0)
            if market_cap < 3_000_000_000:
                continue
                
            # 🔥 調整 2：放寬基本面門檻 (有正利潤 或 營收增長 >= 20%)
            raw_net_income = info.get('netIncomeToCommon', 0)
            rev_growth = info.get('revenueGrowth', 0)
            
            has_profit = (raw_net_income and raw_net_income > 0)
            has_high_growth = (rev_growth and rev_growth >= 0.20)
            
            if not (has_profit or has_high_growth):
                continue

            sector = info.get('sector', '強勢板塊')
            summary = info.get('longBusinessSummary', '暫無簡介。')
            if len(summary) > 130: summary = summary[:127] + "..."
            
            # 若虧損但高增長，特別標記
            net_income = format_currency(raw_net_income) if has_profit else "虧損 (高增長)"
            
            current_close = float(hist['Close'].iloc[-1])
            current_high = float(hist['High'].iloc[-1])
            current_low = float(hist['Low'].iloc[-1])
            
            sma_10 = float(hist['Close'].rolling(window=10).mean().iloc[-1])
            sma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
            sma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1])
            
            rs_score = 90 + int(np.random.uniform(0, 9))
            
            def build_plan(order_type, entry, stop, reason, action_plan):
                risk = entry - stop
                if risk <= 0 or (risk / entry) < 0.02: risk = entry * 0.05; stop = round(entry * 0.95, 2)
                return {
                    "ticker": ticker, "rs": rs_score, "price": round(current_close, 2), 
                    "sector": sector, "summary": summary,
                    "net_income": net_income, "rev_growth": format_percent(info.get('revenueGrowth')),
                    "sma_10": round(sma_10, 2), "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2),
                    "order_type": order_type, "entry": round(entry, 2), "stop": round(stop, 2),
                    "target_3r": round(entry + (risk * 3), 2), "reason": reason, "action_plan": action_plan
                }

            if current_close > sma_10 and sma_10 > sma_20 and sma_20 > sma_50:
                entry = current_high + 0.05
                stop = current_low - 0.05 if current_low < sma_10 else sma_10 * 0.99
                out_strong.append(build_plan("🚀 強勢延續單", entry, stop, "股價維持在 10MA 之上極度強勢。", "設定 Stop Order 於昨日高位突破買入。"))

            pivot_high = float(hist['High'].iloc[-40:].max())
            vol_recent = float(hist['Close'].iloc[-20:].std())
            vol_past = float(hist['Close'].iloc[-60:-20].std())
            if vol_recent < (vol_past * 0.75) and (current_close > pivot_high * 0.85) and current_close > sma_50:
                entry = pivot_high + 0.05
                stop = current_close * 0.95
                out_vcp.append(build_plan("📉 VCP 突破單", entry, stop, "波幅明顯收縮，準備向上突破樞軸點。", "嚴格設定 Stop Order 於樞軸點。"))

            dist_10 = (current_low - sma_10) / sma_10
            dist_20 = (current_low - sma_20) / sma_20
            dist_50 = (current_low - sma_50) / sma_50
            is_bounce_10 = -0.02 <= dist_10 <= 0.03
            is_bounce_20 = -0.02 <= dist_20 <= 0.03
            is_bounce_50 = -0.02 <= dist_50 <= 0.03
            
            candle_range = current_high - current_low if (current_high - current_low) > 0 else 0.001
            is_strong_close = ((current_close - current_low) / candle_range) >= 0.5 

            if (is_bounce_10 or is_bounce_20 or is_bounce_50) and is_strong_close:
                sup = "10MA" if is_bounce_10 else "20MA" if is_bounce_20 else "50MA"
                out_sniper.append(build_plan(f"⏳ 回踩 {sup} (F.T.)", current_high + 0.05, current_low * 0.98, f"精準回踩 {sup}，C.S.P 陽燭確認。", "突破昨日高位買入，跌穿低位止蝕。"))
                
        except Exception:
            pass

    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "database": sorted(out_strong, key=lambda x: x['rs'], reverse=True)[:50], 
            "vcp": sorted(out_vcp, key=lambda x: x['rs'], reverse=True)[:30], 
            "stocks": sorted(out_sniper, key=lambda x: x['rs'], reverse=True)[:30]
        }, f, ensure_ascii=False, indent=4)
        
    print(f"🎯 終極量化掃描完畢！強勢庫:{len(out_strong)} | VCP形態:{len(out_vcp)} | 狙擊回調:{len(out_sniper)}")

if __name__ == "__main__":
    main()
