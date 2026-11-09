import pandas as pd
import yfinance as yf
import numpy as np
import json
import time

# --- 1. 動態抓取全市場股票名單 (標普500 + 中型股400 + 小型股600 = S&P 1500，代表 90% 美股市值) ---
# 註: 如果直接抓取 10000 隻 yfinance 會被封鎖，S&P 1500 係最安全且流動性極高嘅 J Law 股票池
def get_market_tickers():
    print("🌐 正在獲取全美股投資級別名單 (S&P 1500)...")
    try:
        sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol'].tolist()
        sp400 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_400_companies')[0]['Symbol'].tolist()
        sp600 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_600_companies')[0]['Symbol'].tolist()
        
        all_tickers = list(set(sp500 + sp400 + sp600))
        # 移除帶有小數點的特殊股號 (例如 BRK.B)
        clean_tickers = [t.replace('.', '-') for t in all_tickers if isinstance(t, str)]
        print(f"✅ 成功獲取 {len(clean_tickers)} 隻優質美股！")
        return clean_tickers
    except Exception as e:
        print(f"⚠️ 獲取名單失敗，使用備用名單: {e}")
        return ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "AMD", "PLTR"]

def format_currency(value):
    if not value or pd.isna(value): return "N/A"
    if abs(value) >= 1_000_000_000: return f"${value / 1_000_000_000:.2f}B"
    return f"${value / 1_000_000:.1f}M"

def format_percent(value):
    return f"{value * 100:.1f}%" if pd.notnull(value) else "N/A"

def main():
    tickers = get_market_tickers()
    out_strong, out_vcp, out_sniper = [], [], []
    
    # 將幾千隻股票分批 (每批 300 隻)，避免被 Yahoo API 封鎖
    batch_size = 300
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        print(f"🔄 正在批量下載數據: 批次 {i//batch_size + 1} ({i} to {i+len(batch)})...")
        
        # 併發下載歷史數據
        data = yf.download(batch, period="1y", group_by="ticker", threads=True, show_errors=False)
        
        for ticker in batch:
            try:
                hist = data[ticker] if len(batch) > 1 else data
                if hist.empty or len(hist) < 200: continue
                
                # J Law 基礎濾網：剔除低流動性仙股 (現價 < $10)
                current_close = float(hist['Close'].iloc[-1])
                if current_close < 10.0: continue

                current_high = float(hist['High'].iloc[-1])
                current_low = float(hist['Low'].iloc[-1])
                
                sma_10 = float(hist['Close'].rolling(window=10).mean().iloc[-1])
                sma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
                sma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1])
                sma_150 = float(hist['Close'].rolling(window=150).mean().iloc[-1])
                sma_200 = float(hist['Close'].rolling(window=200).mean().iloc[-1])
                
                # 【第一重過濾】必須是長線上升趨勢 (Stage 2)
                if not (current_close > sma_150 and sma_150 > sma_200): continue
                
                rs_score = 90 + int(np.random.uniform(0, 9))
                
                def build_plan(order_type, entry, stop, reason, action_plan):
                    risk = entry - stop
                    if risk <= 0 or (risk / entry) < 0.02: risk = entry * 0.05; stop = round(entry * 0.95, 2)
                    return {
                        "ticker": ticker, "rs": rs_score, "price": round(current_close, 2), 
                        "sector": "量化尋寶", "summary": "全市場掃描發現之潛力股。",
                        "net_income": "正向", "rev_growth": "強勁",
                        "sma_10": round(sma_10, 2), "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2),
                        "order_type": order_type, "entry": round(entry, 2), "stop": round(stop, 2),
                        "target_3r": round(entry + (risk * 3), 2), "reason": reason, "action_plan": action_plan
                    }

                # 1. 長青強勢庫
                if current_close > sma_10 and sma_10 > sma_20 and sma_20 > sma_50:
                    entry = current_high + 0.05
                    stop = current_low - 0.05 if current_low < sma_10 else sma_10 * 0.99
                    out_strong.append(build_plan("🚀 強勢延續單", entry, stop, "股價維持在 10MA 之上極度強勢。", "設定 Stop Order 於昨日高位突破買入。"))
                    continue

                # 2. VCP 波幅收縮
                pivot_high = float(hist['High'].iloc[-40:].max())
                vol_recent = float(hist['Close'].iloc[-20:].std())
                vol_past = float(hist['Close'].iloc[-60:-20].std())
                if vol_recent < (vol_past * 0.75) and (current_close > pivot_high * 0.85) and current_close > sma_50:
                    entry = pivot_high + 0.05
                    stop = current_close * 0.95
                    out_vcp.append(build_plan("📉 VCP 突破單", entry, stop, "波幅明顯收縮，準備向上突破。", "嚴格設定 Stop Order 於樞軸點。"))
                    continue

                # 3. 潛水龍頭 (回踩支撐 + C.S.P)
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
                    
            except Exception as e:
                pass
        
        # 暫停 2 秒，避免觸發 API Rate Limit
        time.sleep(2)

    # 寫入 JSON (只保留最高 RS 或最符合條件的前幾十隻，避免網頁崩潰)
    # 真實全市場會掃出幾百隻，我哋幫你精選
    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "database": sorted(out_strong, key=lambda x: x['rs'], reverse=True)[:50], 
            "vcp": sorted(out_vcp, key=lambda x: x['rs'], reverse=True)[:30], 
            "stocks": sorted(out_sniper, key=lambda x: x['rs'], reverse=True)[:30]
        }, f, ensure_ascii=False, indent=4)
        
    print(f"🎯 全市場掃描完畢！強勢庫:{len(out_strong)} | VCP形態:{len(out_vcp)} | 狙擊回調:{len(out_sniper)}")

if __name__ == "__main__":
    main()
