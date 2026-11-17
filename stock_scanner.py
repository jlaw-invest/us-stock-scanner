import pandas as pd
import yfinance as yf
import numpy as np
import json
import time
import requests
from scipy.stats import rankdata

def get_all_us_tickers():
    print("🌐 正在獲取全美股市場名單...")
    tickers = set()
    try:
        # 使用中性系統名稱，避免任何人物品牌關聯
        headers = {"User-Agent": "AlphaPulse-MarketScanner contact@alphapulse-data.com"}
        res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=10)
        data = res.json()
        for v in data.values():
            tickers.add(v['ticker'].replace('.', '-'))
        print(f"✅ 成功從 SEC 獲取 {len(tickers)} 隻股票。")
    except Exception as e:
        print(f"⚠️ SEC 列表獲取失敗: {e}")

    if len(tickers) < 1000:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            for url in [
                'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
                'https://en.wikipedia.org/wiki/List_of_S%26P_400_companies',
                'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
            ]:
                df = pd.read_html(requests.get(url, headers=headers).text)[0]
                tickers.update(df['Symbol'].str.replace('.', '-').tolist())
        except:
            pass
        
    if not tickers:
        tickers.update(["AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "AVGO", "CRWD", "PLTR", "MPWR"])
        
    return list(tickers)

def format_currency(value):
    if not value or pd.isna(value): return "N/A"
    if abs(value) >= 1_000_000_000: return f"${value / 1_000_000_000:.2f}B"
    return f"${value / 1_000_000:.1f}M"

def format_percent(value):
    return f"{value * 100:.1f}%" if pd.notnull(value) else "N/A"

def calculate_raw_momentum(hist_data):
    try:
        if len(hist_data) < 252:
            return None
        
        current_close = float(hist_data['Close'].iloc[-1])
        close_q1_ago = float(hist_data['Close'].iloc[-63])
        close_q2_ago = float(hist_data['Close'].iloc[-126])
        close_q3_ago = float(hist_data['Close'].iloc[-189])
        close_q4_ago = float(hist_data['Close'].iloc[-252])
        
        if close_q1_ago == 0 or close_q2_ago == 0 or close_q3_ago == 0 or close_q4_ago == 0:
            return None

        perf_q1 = (current_close - close_q1_ago) / close_q1_ago
        perf_q2 = (close_q1_ago - close_q2_ago) / close_q2_ago
        perf_q3 = (close_q2_ago - close_q3_ago) / close_q3_ago
        perf_q4 = (close_q3_ago - close_q4_ago) / close_q4_ago
        
        weighted_momentum = (perf_q1 * 0.40) + (perf_q2 * 0.20) + (perf_q3 * 0.20) + (perf_q4 * 0.20)
        if pd.isna(weighted_momentum) or np.isinf(weighted_momentum):
            return None
        return weighted_momentum
    except:
        return None

def main():
    all_tickers = get_all_us_tickers()
    momentum_scores = {}
    
    out_leaders, out_squeeze, out_pullback = [], [], []
    batch_size = 300
    candidates = []
    
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        print(f"🔄 正在批量掃描客觀技術數據: 批次 {i//batch_size + 1} ({i} to {i+len(batch)})...")
        
        try:
            data = yf.download(batch, period="1y", group_by="ticker", threads=True, progress=False)
            
            for ticker in batch:
                try:
                    hist = data[ticker] if len(batch) > 1 else data
                    if hist.empty or len(hist) < 252: continue
                    
                    current_close = float(hist['Close'].iloc[-1])
                    prev_close = float(hist['Close'].iloc[-2])
                    avg_vol_20 = float(hist['Volume'].iloc[-20:].mean())
                    turnover_m = (current_close * avg_vol_20) / 1_000_000
                    
                    if current_close < 30.0 or turnover_m < 15.0:
                        continue
                        
                    raw_mom = calculate_raw_momentum(hist)
                    if raw_mom is not None:
                        momentum_scores[ticker] = raw_mom

                    current_high = float(hist['High'].iloc[-1])
                    current_low = float(hist['Low'].iloc[-1])
                    change_pct = ((current_close - prev_close) / prev_close) * 100
                    
                    sma_10 = float(hist['Close'].rolling(window=10).mean().iloc[-1])
                    sma_20 = float(hist['Close'].rolling(window=20).mean().iloc[-1])
                    sma_50 = float(hist['Close'].rolling(window=50).mean().iloc[-1])
                    sma_150 = float(hist['Close'].rolling(window=150).mean().iloc[-1])
                    sma_200 = float(hist['Close'].rolling(window=200).mean().iloc[-1])
                    
                    # 14日平均真實波幅 (ATR) - 純客觀波動率指標
                    high_low = hist['High'] - hist['Low']
                    atr_14 = float(high_low.rolling(window=14).mean().iloc[-1])
                    high_40d = float(hist['High'].iloc[-40:].max())
                    
                    is_uptrend = (current_close > sma_150 and sma_150 > sma_200)
                    
                    def build_objective_record(pattern_tag, tech_summary):
                        return {
                            "ticker": ticker,
                            "m_rank": 0,
                            "price": round(current_close, 2),
                            "change_pct": round(change_pct, 2),
                            "sma_10": round(sma_10, 2),
                            "sma_20": round(sma_20, 2),
                            "sma_50": round(sma_50, 2),
                            "high_40d": round(high_40d, 2),
                            "atr_14": round(atr_14, 2),
                            "turnover_m": round(turnover_m, 1),
                            "pattern_tag": pattern_tag,
                            "tech_summary": tech_summary
                        }

                    matched = False
                    # 1. 強勢動能多頭排列
                    if is_uptrend and current_close > sma_10 and sma_10 > sma_20 and sma_20 > sma_50:
                        candidates.append({
                            "type": "database",
                            "data": build_objective_record(
                                "均線多頭排列",
                                f"收市價 (${current_close:.2f}) 企穩於 10MA (${sma_10:.2f})、20MA (${sma_20:.2f}) 及 50MA (${sma_50:.2f}) 之上，短中長期均線呈順序向上排列。"
                            )
                        })
                        matched = True

                    # 2. 波幅收斂形態觀察
                    vol_recent = float(hist['Close'].iloc[-20:].std())
                    vol_past = float(hist['Close'].iloc[-60:-20].std())
                    if vol_recent < (vol_past * 0.85) and (current_close > high_40d * 0.80) and current_close > sma_50:
                        candidates.append({
                            "type": "vcp",
                            "data": build_objective_record(
                                "波幅收斂區間",
                                f"近 20 日收市價標準差較前 40 日收窄逾 15%，目前價格處於 40 日區間高點 (${high_40d:.2f}) 附近整固，並維持於 50MA 之上。"
                            )
                        })
                        matched = True

                    # 3. 均線支撐回測觀察
                    if is_uptrend and not matched:
                        dist_10 = (current_low - sma_10) / sma_10
                        dist_20 = (current_low - sma_20) / sma_20
                        dist_50 = (current_low - sma_50) / sma_50
                        
                        is_near_10 = -0.02 <= dist_10 <= 0.03
                        is_near_20 = -0.02 <= dist_20 <= 0.03
                        is_near_50 = -0.02 <= dist_50 <= 0.03
                        
                        candle_range = current_high - current_low if (current_high - current_low) > 0 else 0.001
                        is_upper_close = ((current_close - current_low) / candle_range) >= 0.5 

                        if (is_near_10 or is_near_20 or is_near_50) and is_upper_close:
                            ma_label = "10MA" if is_near_10 else "20MA" if is_near_20 else "50MA"
                            candidates.append({
                                "type": "stocks",
                                "data": build_objective_record(
                                    f"回測 {ma_label} 區間",
                                    f"盤中低位曾測試 {ma_label} 附近區域，當日收市價位於日內波幅上半部，維持中長線上升趨勢結構。"
                                )
                            })
                except:
                    pass
        except:
            pass
        
        time.sleep(1)

    print(f"📊 正在計算全市場動能百分位 (基於 {len(momentum_scores)} 隻美股數據)...")
    ticker_to_rank = {}
    if momentum_scores:
        valid_scores = {k: v for k, v in momentum_scores.items() if not pd.isna(v) and not np.isinf(v)}
        if valid_scores:
            tickers_list = list(valid_scores.keys())
            scores_list = list(valid_scores.values())
            ranks = rankdata([-s for s in scores_list], method='min')
            total_stocks = len(scores_list)
            for t, r in zip(tickers_list, ranks):
                percentile = ((total_stocks - r) / (total_stocks - 1)) * 98 + 1
                if not pd.isna(percentile) and not np.isinf(percentile):
                    ticker_to_rank[t] = int(round(percentile))

    for item in candidates:
        ticker = item["data"]["ticker"]
        item["data"]["m_rank"] = ticker_to_rank.get(ticker, 50)
        
        try:
            info = yf.Ticker(ticker).info
            sector = info.get('sector', '美股市場')
        except:
            sector = "美股市場"
        
        item["data"]["sector"] = sector
        
        if item["type"] == "database": out_leaders.append(item["data"])
        elif item["type"] == "vcp": out_squeeze.append(item["data"])
        elif item["type"] == "stocks": out_pullback.append(item["data"])

    total_found = len(out_leaders) + len(out_squeeze) + len(out_pullback)
    print(f"🎯 掃描完畢！動能強勢庫:{len(out_leaders)} | 波幅收斂:{len(out_squeeze)} | 均線回測:{len(out_pullback)} | 總計:{total_found}")

    if total_found < 3:
        print("⚠️ 警告：數據異常或過少，啟動防空網保護，放棄覆蓋！")
        return

    with open("stocks_data.json", "w", encoding="utf-8") as f:
        json.dump({
            "database": sorted(out_leaders, key=lambda x: x['m_rank'], reverse=True)[:50], 
            "vcp": sorted(out_squeeze, key=lambda x: x['m_rank'], reverse=True)[:50], 
            "stocks": sorted(out_pullback, key=lambda x: x['m_rank'], reverse=True)[:50]
        }, f, ensure_ascii=False, indent=4)
    print("✅ 客觀市場數據已安全寫入 stocks_data.json！")

if __name__ == "__main__":
    main()
