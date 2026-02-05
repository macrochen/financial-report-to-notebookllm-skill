#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Format Converter: PDF/HTML to Markdown
"""

import os
import pymupdf4llm
import html2text
from bs4 import BeautifulSoup

def pdf_to_markdown(pdf_path: str) -> str:
    """Convert PDF to Markdown, returns md file path"""
    md_path = pdf_path.rsplit(".", 1)[0] + ".md"
    print(f"📝 Converting to Markdown: {os.path.basename(pdf_path)}")
    
    try:
        # Use pymupdf4llm for high-quality table extraction
        md_text = pymupdf4llm.to_markdown(pdf_path)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        return md_path
    except Exception as e:
        print(f"❌ PDF to MD failed: {e}")
        return None

def html_to_markdown(html_content: str, output_path: str) -> str:
    """Convert HTML content to Markdown, returns md file path"""
    print(f"📝 Converting HTML to Markdown...")
    
    try:
        # Pre-process with BeautifulSoup to remove scripts/styles
        soup = BeautifulSoup(html_content, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
            
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0 # No wrapping
        
        md_text = h.handle(str(soup))
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        return output_path
    except Exception as e:
        print(f"❌ HTML to MD failed: {e}")
        return None
