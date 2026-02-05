#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
US Stock Downloader (SEC EDGAR) - Fixed JSON Path
"""

import os
import sys
import json
import httpx
import time
import tempfile
from converter import html_to_markdown

class SecEdgarDownloader:
    def __init__(self):
        self.headers = {
            "User-Agent": "Independent Equity Analyst (analyst@research-firm.com)",
            "Accept-Encoding": "gzip, deflate",
        }
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def get_cik(self, ticker: str) -> str:
        ticker = ticker.upper()
        print(f"🔍 Looking up CIK for {ticker}...")
        try:
            resp = self.client.get("https://www.sec.gov/files/company_tickers.json", headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.values():
                    if item["ticker"] == ticker:
                        cik = str(item["cik_str"]).zfill(10)
                        print(f"✅ Found CIK: {cik}")
                        return cik
        except Exception as e:
            print(f"❌ CIK lookup error: {e}")
        return None

    def get_filings(self, cik: str):
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        print(f"🔍 Fetching filings for CIK {cik}...")
        try:
            resp = self.client.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                # CORRECT PATH: data['filings']['recent']
                return data.get("filings", {}).get("recent", {})
            print(f"❌ Filing fetch failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"❌ Filing fetch error: {e}")
        return None

    def download_filing(self, cik: str, accession_number: str, primary_document: str, output_dir: str, title: str) -> str:
        acc_no_clean = accession_number.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_clean}/{primary_document}"
        
        md_filename = f"{title}.md"
        output_path = os.path.join(output_dir, md_filename)
        
        try:
            print(f"📥 Downloading SEC filing: {title}")
            resp = self.client.get(url, headers=self.headers)
            if resp.status_code == 200:
                return html_to_markdown(resp.text, output_path)
        except Exception as e:
            print(f"❌ SEC Download error: {e}")
        return None

    def get_reports(self, ticker: str, output_dir: str) -> list:
        cik = self.get_cik(ticker)
        if not cik: return []
            
        recent = self.get_filings(cik)
        if not recent: return []
            
        forms = recent.get("form", [])
        acc_nos = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        dates = recent.get("reportDate", [])
        
        results = []
        ten_k_count = 0
        
        print(f"📊 Analyzing {len(forms)} filings...")
        
        for i in range(len(forms)):
            form = forms[i]
            if form == "10-K" and ten_k_count < 5:
                res = self.download_filing(cik, acc_nos[i], docs[i], output_dir, f"{ticker}_10K_{dates[i]}")
                if res:
                    results.append(res)
                    ten_k_count += 1
            elif form == "10-Q" and not any("_10Q_" in f for f in results):
                res = self.download_filing(cik, acc_nos[i], docs[i], output_dir, f"{ticker}_10Q_{dates[i]}")
                if res:
                    results.append(res)
            
            if ten_k_count >= 5 and any("_10Q_" in f for f in results):
                break
            time.sleep(0.5) 
            
        return results

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    downloader = SecEdgarDownloader()
    output = tempfile.mkdtemp()
    files = downloader.get_reports(ticker, output)
    print(f"DONE: {len(files)} files.")