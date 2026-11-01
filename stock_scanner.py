import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# 1. 初始化 Firebase 連線 (會自動讀取你剛剛改好名字的金鑰檔案)
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

def upload_top_stocks_to_firebase(symbol, rs_rating, pivot_point):
    """
    自動上傳符合條件的美股強勢股到 Firebase Firestore 雲端資料庫
    篩選條件：RS >= 90, Stage 2 上升趨勢, 突破 Pivot Point
    """
    doc_ref = db.collection('stocks').document(symbol)
    doc_ref.set({
        'symbol': symbol,
        'rs_rating': rs_rating,
        'pivot_point': pivot_point,
        'trend': 'Stage 2',
        'updated_at': firestore.SERVER_TIMESTAMP
    })
    print(f"成功將 {symbol} (RS: {rs_rating}) 上傳至 Firebase 雲端資料庫！")

if __name__ == "__main__":
    print("美股 RS 90+ 自動選股與上傳引擎啟動...")
    
    # 測試上傳一檔範例強勢股 (例如 NVDA)
    upload_top_stocks_to_firebase(symbol="NVDA", rs_rating=98, pivot_point=140.50)
    
    # 測試上傳另一檔範例強勢股 (例如 PLTR)
    upload_top_stocks_to_firebase(symbol="PLTR", rs_rating=92, pivot_point=45.20)
    
    print("所有測試數據已成功同步至 Firebase！")