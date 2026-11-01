name: Daily US Stock Scanner

on:
  schedule:
    - cron: '0 22 * * 1-5'
  workflow_dispatch:

jobs:
  run-scanner:
    runs-on: ubuntu-latest
    
    steps:
      - name: 取得程式碼
        uses: actions/checkout@v4
        
      - name: 設定 Python 環境
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          
      - name: 安裝必要套件
        run: |
          python -m pip install --upgrade pip
          pip install pandas yfinance numpy firebase-admin
          
      - name: 執行量化選股引擎
        run: python stock_scanner.py
        
      - name: 儲存並推送 JSON 數據到網頁
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add stocks_data.json
          git commit -m "Auto-update stocks_data.json" || echo "No changes to commit"
          git push