#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HK Stock Downloader (HKEXnews) - Ultimate Fixed Version
Correctly clicks Search and captures results using multiple fallback methods.
"""

import os
import sys
import httpx
import tempfile
import time
import re
from playwright.sync_api import sync_playwright

class HkexDownloader:
    RECENT_REPORT_YEARS = 5

    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.last_company_name = None
        self.last_stock_code = None
        self.include_keywords = [
            "年報",
            "年报",
            "年度報告",
            "年度报告",
            "全年業績",
            "全年业绩",
            "年度業績",
            "年度业绩",
            "全年業績公告",
            "全年业绩公告",
            "年度業績公告",
            "年度业绩公告",
            "末期業績",
            "末期业绩",
            "中期報告",
            "中期报告",
            "中期業績",
            "中期业绩",
            "中期報告書",
            "季度報告",
            "季度报告",
            "第一季度報告",
            "第三季度報告",
            "annual results",
            "final results",
            "full year results",
            "year-end results",
        ]
        self.exclude_keywords = [
            "esg",
            "環境、社會及管治",
            "环境、社会及管治",
            "可持續發展",
            "可持续发展",
            "sustainability",
            "sustainable",
            "governance",
            "摘要",
            "更正",
            "補充",
            "补充",
            "通函",
        ]

    def _extract_company_name_from_suggestion(self, suggestion_text: str, stock_code: str) -> str | None:
        """Parse the company name from HKEX autocomplete text."""
        text = re.sub(r"\s+", " ", (suggestion_text or "")).strip()
        normalized_code = (stock_code or "").zfill(5)
        if not text:
            return None

        patterns = [
            rf"^{normalized_code}\s*[-–—]?\s*(.+)$",
            rf"^(.+?)\s*\(?{normalized_code}\)?$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" -–—()")
                if candidate and candidate.upper() != f"HK_{normalized_code}":
                    return candidate

        parts = [part.strip(" -–—()") for part in re.split(r"\s*[-–—]\s*", text) if part.strip()]
        for part in parts:
            if normalized_code not in part and part.upper() != f"HK_{normalized_code}":
                return part
        return None

    def get_company_name(self, stock_code: str) -> str | None:
        """Resolve HK stock company name from the HKEX search autocomplete."""
        normalized_code = (stock_code or "").zfill(5)
        if self.last_stock_code == normalized_code and self.last_company_name:
            return self.last_company_name

        url = "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh"
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, slow_mo=300)
                context = browser.new_context(user_agent=self.user_agent, viewport={"width": 1280, "height": 900})
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.click("#searchStockCode")
                page.type("#searchStockCode", normalized_code, delay=120)
                suggestion = page.locator(".autocomplete-suggestion").first
                suggestion.wait_for(timeout=10000)
                suggestion_text = suggestion.inner_text().strip()
                company_name = self._extract_company_name_from_suggestion(suggestion_text, normalized_code)
                if company_name:
                    self.last_stock_code = normalized_code
                    self.last_company_name = company_name
                return company_name
            except Exception:
                return None
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    def is_financial_report_title(self, title: str) -> bool:
        """Keep annual/interim/quarterly/final-results reports and reject ESG-like filings."""
        normalized = (title or "").strip()
        normalized_lower = normalized.lower()
        if not normalized:
            return False
        if any(keyword.lower() in normalized_lower for keyword in self.exclude_keywords):
            return False

        # 港股很多全年披露使用“业绩结果/末期业绩”而不是“年度报告”命名。
        # 这里把这些结果公告纳入，但仍要求它们同时带有明确的期间信号，避免误抓普通公告。
        has_include_keyword = any(keyword.lower() in normalized_lower for keyword in self.include_keywords)
        has_period_signal = any(
            marker in normalized_lower
            for marker in (
                "年",
                "年度",
                "全年",
                "quarter",
                "interim",
                "final",
                "full year",
                "year ended",
                "year-end",
            )
        )
        if has_include_keyword and has_period_signal:
            return True

        return False

    def add_report(self, reports: list, title: str, full_url: str):
        """Add a report if it passes title filtering and is not duplicated."""
        if not self.is_financial_report_title(title):
            return
        if any(item["url"] == full_url for item in reports):
            return
        print(f"  ✅ 捕获: {title}")
        reports.append({"title": title, "url": full_url})

    def collect_reports_from_current_page(self, page, reports: list, limit: int | None = None):
        """Collect matching PDF links from the current results page."""
        links = page.query_selector_all(".doc-link a, .table-container a[href*='.pdf']")
        print(f"🔎 扫描到 {len(links)} 个潜在链接...")

        for link_el in links:
            try:
                title = link_el.inner_text().strip()
                href = link_el.get_attribute("href")
                if not href or ".pdf" not in href.lower():
                    continue

                row_text = ""
                try:
                    row = link_el.locator("xpath=ancestor::tr[1]")
                    if row.count():
                        row_text = row.inner_text().strip()
                except Exception:
                    row_text = ""

                title = row_text or title
                full_url = "https://www1.hkexnews.hk" + href if href.startswith("/") else href

                self.add_report(reports, title, full_url)
            except Exception:
                continue
            if limit and len(reports) >= limit:
                break

        return links

    def extract_report_year(self, title: str) -> int | None:
        """Extract a 4-digit report year from a filing title."""
        text = title or ""
        match = re.search(r"(20\d{2})", text)
        if not match:
            chinese_year = self._extract_chinese_digit_year(text)
            return chinese_year
        return int(match.group(1))

    def _extract_chinese_digit_year(self, title: str) -> int | None:
        """Extract years written as Chinese digits, such as 二零二五年."""
        digit_map = {
            "零": "0",
            "〇": "0",
            "一": "1",
            "二": "2",
            "三": "3",
            "四": "4",
            "五": "5",
            "六": "6",
            "七": "7",
            "八": "8",
            "九": "9",
        }
        match = re.search(r"([〇零一二三四五六七八九]{4})年", title or "")
        if not match:
            return None
        numeric = "".join(digit_map.get(ch, "") for ch in match.group(1))
        if len(numeric) != 4 or not numeric.startswith("20"):
            return None
        return int(numeric)

    def is_annual_report_title(self, title: str) -> bool:
        """Detect formal annual report filings."""
        normalized = (title or "").lower()
        return any(keyword in normalized for keyword in ("年報", "年报", "年度報告", "年度报告"))

    def is_annual_results_title(self, title: str) -> bool:
        """Detect annual/final-results style filings used before the annual report is published."""
        normalized = (title or "").lower()
        return any(
            keyword in normalized
            for keyword in (
                "全年業績",
                "全年业绩",
                "年度業績",
                "年度业绩",
                "末期業績",
                "末期业绩",
                "annual results",
                "final results",
                "full year results",
                "year-end results",
            )
        )

    def dedupe_reports_with_annual_priority(self, reports: list) -> list:
        """Prefer formal annual reports; keep annual-results filings only when that year lacks an annual report."""
        annual_report_years = {
            year
            for item in reports
            if (year := self.extract_report_year(item.get("title", ""))) is not None
            and self.is_annual_report_title(item.get("title", ""))
        }

        filtered = []
        for item in reports:
            title = item.get("title", "")
            year = self.extract_report_year(title)
            if year is not None and year in annual_report_years and self.is_annual_results_title(title):
                print(f"  ↪️ 跳过同年度业绩公告（已有正式年报）: {title}")
                continue
            filtered.append(item)
        return filtered

    def keep_recent_report_years(self, reports: list, years: int | None = None) -> list:
        """Keep only reports from the most recent N available report years."""
        if not reports:
            return reports

        window = years or self.RECENT_REPORT_YEARS
        available_years = sorted(
            {
                year
                for item in reports
                if (year := self.extract_report_year(item.get("title", ""))) is not None
            },
            reverse=True,
        )
        if not available_years:
            return reports

        kept_years = set(available_years[:window])
        filtered = []

        for item in reports:
            title = item.get("title", "")
            year = self.extract_report_year(title)
            if year is None:
                continue
            if year in kept_years:
                filtered.append(item)
            else:
                print(f"  ↪️ 跳过超出近{window}年范围的历史财报: {title}")

        filtered.sort(
            key=lambda item: (
                self.extract_report_year(item.get("title", "")) or 0,
                item.get("title", ""),
            ),
            reverse=True,
        )
        return filtered

    def find_reports(self, stock_code: str) -> list:
        stock_code = stock_code.zfill(5)
        print(f"🚀 启动终极匹配模式: 抓取港股 {stock_code}...")
        
        reports = []
        url = "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh"
        
        with sync_playwright() as p:
            # Default to headless mode so the downloader can run in sandboxed
            # or CI-like environments where a headed browser is unavailable.
            browser = p.chromium.launch(headless=True, slow_mo=1000)
            context = browser.new_context(user_agent=self.user_agent, viewport={'width': 1280, 'height': 1000})
            page = context.new_page()
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # 1. 第一步：录入代码并选中联想词
                print("1️⃣ 录入股份代号...")
                page.click("#searchStockCode")
                page.type("#searchStockCode", stock_code, delay=150)
                suggestion = page.locator(".autocomplete-suggestion").first
                suggestion.wait_for(timeout=10000)
                suggestion_text = suggestion.inner_text().strip()
                self.last_stock_code = stock_code
                self.last_company_name = self._extract_company_name_from_suggestion(suggestion_text, stock_code)
                suggestion.click()
                print("✅ 已选中公司")

                # 2. 第二步：先搜全部披露，补抓“全年/年度业绩公告”。
                # 港股“全年/年度业绩公告”常挂在 Announcements and Notices / Final Results，
                # 如果先限定到“財務報表”分类，反而会把真正的全年结果挡掉。
                print("2️⃣ 保持全量披露搜索，补抓全年/年度业绩公告...")

                # 3. 第三步：【关键点击】点击搜寻按钮
                print("3️⃣ 点击深蓝色‘搜尋’按钮...")
                search_btn = page.locator(".filter__btn-applyFilters-js.btn-blue").first
                search_btn.click()

                # 4. 等待数据加载
                print("⏳ 正在等待数据加载 (10s)...")
                # 显式等待 URL 跳转或特定元素
                try:
                    page.wait_for_selector(".table-container, .doc-link", timeout=15000)
                except:
                    print("⚠️ 自动同步超时，执行硬等待...")
                
                time.sleep(5)
                print(f"📍 当前 URL: {page.url}")

                # 5. 提取链接 (第一轮：全量披露)
                print("📋 正在提取符合条件的报表链接（全量披露）...")
                links = self.collect_reports_from_current_page(page, reports)

                # 6. 第二轮：再切到“財務報表”分类，补足历史年报/中报。
                print("6️⃣ 切换到‘財務報表 / 環境、社會及管治資料’补抓历史财报...")
                page.click("#tier1-select .combobox-field")
                page.click(".combobox-boundlist .droplist-item[data-value='rbAfter2006']")
                page.click("#rbAfter2006 .combobox-field")
                time.sleep(1)
                page.click("li[data-value='40000']")
                try:
                    page.click("li[data-value='40000'] li[data-value='-2']", timeout=5000)
                except Exception:
                    page.evaluate("document.querySelector('li[data-value=\"40000\"] li[data-value=\"-2\"]')?.click()")
                page.keyboard.press("Escape")
                time.sleep(1)
                search_btn = page.locator(".filter__btn-applyFilters-js.btn-blue").first
                search_btn.click()
                try:
                    page.wait_for_selector(".table-container, .doc-link", timeout=15000)
                except Exception:
                    print("⚠️ 财务报表分类结果等待超时，继续尝试读取当前页面...")
                time.sleep(5)
                print("📋 正在提取符合条件的报表链接（财务报表分类）...")
                self.collect_reports_from_current_page(page, reports)

                # 方法 B: 源码正则提取 (降级兜底)
                if not reports:
                    print("🔥 触发降级方案：从页面源码提取标题和链接，并继续执行财报过滤...")
                    content = page.content()
                    pdf_matches = re.findall(
                        r'href="(/listedco/listconews/sehk/[^"]+\.pdf)"[^>]*>(.*?)</a>',
                        content,
                        re.IGNORECASE | re.DOTALL,
                    )
                    for pdf_url, raw_title in pdf_matches:
                        full_url = "https://www1.hkexnews.hk" + pdf_url
                        title = re.sub(r"<[^>]+>", " ", raw_title)
                        title = re.sub(r"\s+", " ", title).strip()
                        self.add_report(reports, title, full_url)

                reports = self.dedupe_reports_with_annual_priority(reports)
                reports = self.keep_recent_report_years(reports)
                print(f"🎉 最终获取到 {len(reports)} 份报表。")
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ 流程异常: {e}")
                page.screenshot(path="hkex_final_crash.png")
            finally:
                browser.close()
                
        return reports

    def download_and_convert(self, reports: list, output_dir: str) -> list:
        results = []
        headers = {"User-Agent": self.user_agent, "Referer": "https://www1.hkexnews.hk/"}
        
        with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
            for r in reports:
                success = False
                for attempt in range(3):
                    try:
                        clean_title = "".join(c for c in r["title"] if c.isalnum() or c in " _-").strip()
                        filename = f"{clean_title}.pdf"
                        filepath = os.path.join(output_dir, filename)
                        
                        print(f"📥 下载 ({attempt+1}/3): {r['title']}")
                        resp = client.get(r["url"])
                        
                        if resp.status_code == 200:
                            # 港股长报转 Markdown 很慢，直接保留 PDF 给 NotebookLM 更稳。
                            if resp.content.startswith(b"%PDF"):
                                with open(filepath, "wb") as f:
                                    f.write(resp.content)
                                results.append(filepath)
                                success = True
                                break
                            else:
                                print(f"⚠️ 下载内容似乎不是有效的 PDF，重试中...")
                        else:
                            print(f"⚠️ 下载失败: HTTP {resp.status_code}")
                        
                        time.sleep(2) # 失败重试等待
                    except Exception as e:
                        print(f"❌ 失败: {e}")
                        time.sleep(2)
                
                if not success:
                    print(f"🚫 放弃下载: {r['title']}")
                time.sleep(1)
        return results

if __name__ == "__main__":
    downloader = HkexDownloader()
    downloader.find_reports("00700")
