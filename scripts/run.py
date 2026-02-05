#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinancialReport2NotebookLLM - Multi-Market Orchestrator
Supports A-share, US, and HK markets with Markdown conversion.
"""

import sys
import os
import json
import tempfile
import shutil
import re

# --- VENV BOOTSTRAP ---
# 彻底解决路径问题：自动寻找并使用本地虚拟环境
script_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.dirname(script_dir)
venv_python = os.path.join(skill_root, ".venv", "bin", "python")

if os.path.exists(venv_python) and sys.executable != venv_python:
    # 如果检测到本地虚拟环境且当前未在使用，则自动重启脚本
    os.execl(venv_python, venv_python, *sys.argv)
# ----------------------

# Add scripts directory to path
sys.path.insert(0, script_dir)

def detect_market(stock_input: str) -> str:
    """Detect market based on input string"""
    # Ticker (US): Letters only
    if re.match(r"^[A-Za-z]+$", stock_input):
        return "US"
    # HK Code: 5 digits (can start with 0)
    if re.match(r"^\d{5}$", stock_input):
        return "HK"
    # A-share Code: 6 digits
    if re.match(r"^\d{6}$", stock_input):
        return "CN"
    # Default to CN name lookup
    return "CN_NAME"

def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <ticker_or_code_or_name>")
        sys.exit(1)

    stock_input = sys.argv[1]
    market = detect_market(stock_input)
    
    # Use a persistent directory based on stock_input to cache downloads
    # This avoids re-downloading if a previous run failed during upload
    base_cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(base_cache_dir, exist_ok=True)
    output_dir = os.path.join(base_cache_dir, f"{market}_{stock_input}")
    
    all_files = []
    stock_name = stock_input
    prompt_file = "financial_analyst_prompt.txt"

    print(f"🔍 Detected Market: {market}")
    
    # Check if we already have files in the cache
    if os.path.exists(output_dir) and os.listdir(output_dir):
        print(f"📦 Found existing reports in cache: {output_dir}")
        all_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".md") or f.endswith(".pdf")]
    
    # If no files found, proceed to download
    if not all_files:
        os.makedirs(output_dir, exist_ok=True)
        if market == "US":
            from us_downloader import SecEdgarDownloader
            downloader = SecEdgarDownloader()
            all_files = downloader.get_reports(stock_input, output_dir)
            prompt_file = "us_financial_analyst_prompt.txt"
            stock_name = stock_input.upper()
        elif market == "HK":
            from hk_downloader import HkexDownloader
            downloader = HkexDownloader()
            reps = downloader.find_reports(stock_input)
            all_files = downloader.download_and_convert(reps, output_dir)
            stock_name = f"HK_{stock_input}"
        else:
            from download import CnInfoDownloader
            downloader = CnInfoDownloader()
            stock_code, stock_info = downloader.find_stock(stock_input)
            if stock_code:
                stock_name = stock_info.get("zwjc", stock_code)
                current_year = 2025 # Simplified for demo
                annual_years = list(range(current_year - 4, current_year))
                all_files = downloader.download_annual_reports(stock_code, annual_years, output_dir)
                periodic = downloader.download_periodic_reports(stock_code, current_year, output_dir)
                all_files.extend(periodic)
            else:
                print(f"❌ Stock not found: {stock_input}")
                if not os.listdir(output_dir):
                    os.rmdir(output_dir)
                sys.exit(1)
    else:
        # Determine stock_name for existing cache
        if market == "US":
            prompt_file = "us_financial_analyst_prompt.txt"
            stock_name = stock_input.upper()
        elif market == "HK":
            stock_name = f"HK_{stock_input}"
        else:
            from download import CnInfoDownloader
            downloader = CnInfoDownloader()
            stock_code, stock_info = downloader.find_stock(stock_input)
            if stock_code:
                stock_name = stock_info.get("zwjc", stock_code)

    if not all_files:
        print("❌ No reports downloaded")
        if os.path.exists(output_dir) and not os.listdir(output_dir):
            os.rmdir(output_dir)
        sys.exit(1)

    print(f"\n✅ Processed {len(all_files)} reports")

    # Upload to NotebookLM
    from upload import create_notebook, upload_all_sources, configure_notebook, cleanup_temp_files
    
    notebook_title = f"{stock_name} 财务深度分析"
    notebook_id = create_notebook(notebook_title)
    
    if notebook_id:
        # Select prompt
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", prompt_file)
        configure_notebook(notebook_id, prompt_path)
        upload_all_sources(notebook_id, all_files)
        
        print(f"\n🎉 COMPLETE! Notebook ID: {notebook_id}")
        # Only cleanup if upload was successful
        cleanup_temp_files(all_files, output_dir)

if __name__ == "__main__":
    main()