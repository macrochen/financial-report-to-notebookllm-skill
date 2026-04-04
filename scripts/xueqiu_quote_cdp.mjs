#!/usr/bin/env node

import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import playwright from '../../opencli-skill/vendor/opencli/node_modules/playwright/index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_STATE_DIR = path.join(process.cwd(), 'outputs', 'opencli-skill', 'shared-xueqiu-background-state');
const DEFAULT_CDP_HTTP_CANDIDATES = [
  process.env.FINANCIAL_REPORT_NOTEBOOKLM_XUEQIU_CDP_HTTP_ENDPOINT,
  process.env.OPENCLI_BG_CDP_HTTP_ENDPOINT,
  'http://127.0.0.1:9222',
  'http://127.0.0.1:9334',
].filter(Boolean);
const HEADLESS_LOG_FILE = path.join(
  process.env.OPENCLI_BG_STATE_DIR || DEFAULT_STATE_DIR,
  'logs',
  'headless.log',
);
const { chromium } = playwright;

function usage() {
  console.error('Usage: xueqiu_quote_cdp.mjs <symbol>');
}

async function resolveWsEndpoint() {
  if (process.env.FINANCIAL_REPORT_NOTEBOOKLM_XUEQIU_CDP_ENDPOINT) {
    return process.env.FINANCIAL_REPORT_NOTEBOOKLM_XUEQIU_CDP_ENDPOINT;
  }
  if (process.env.OPENCLI_BG_CDP_ENDPOINT) {
    return process.env.OPENCLI_BG_CDP_ENDPOINT;
  }

  for (const baseUrl of DEFAULT_CDP_HTTP_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl}/json/version`);
      if (!response.ok) continue;
      const payload = await response.json();
      if (payload?.webSocketDebuggerUrl) {
        return payload.webSocketDebuggerUrl;
      }
    } catch {}
  }

  try {
    const logText = await fs.readFile(HEADLESS_LOG_FILE, 'utf8');
    const match = logText.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[^\s]+/);
    if (match) return match[0];
  } catch {}

  throw new Error(
    `No CDP websocket endpoint available. Tried: ${DEFAULT_CDP_HTTP_CANDIDATES.join(', ')}. ` +
    'Enable Chrome remote debugging for the current browser instance in chrome://inspect/#remote-debugging, ' +
    'or provide FINANCIAL_REPORT_NOTEBOOKLM_XUEQIU_CDP_ENDPOINT.'
  );
}

async function getPage(browser) {
  const contexts = browser.contexts();
  if (contexts.length > 0) {
    const pages = contexts[0].pages();
    if (pages.length > 0) return pages[0];
    return contexts[0].newPage();
  }
  const context = await browser.newContext();
  return context.newPage();
}

async function fetchQuoteInPage(page, symbol) {
  const symbolCandidates = [symbol];
  if (symbol && !symbol.includes(':')) {
    symbolCandidates.push(`US:${symbol}`);
  }

  const endpointCandidates = [
    'https://stock.xueqiu.com/v5/stock/quote.json',
    'https://stock.xueqiu.com/v5/stock/batch/quote.json',
  ];

  return page.evaluate(async ({ symbolCandidates, endpointCandidates, symbol }) => {
    const errors = [];

    for (const endpoint of endpointCandidates) {
      for (const candidate of symbolCandidates) {
        try {
          const url = new URL(endpoint);
          url.searchParams.set('symbol', candidate);
          url.searchParams.set('extend', 'detail');

          const response = await fetch(url.toString(), {
            credentials: 'include',
            headers: {
              Accept: 'application/json,text/plain,*/*',
            },
          });

          if (!response.ok) {
            errors.push(`${endpoint} ${candidate} -> HTTP ${response.status}`);
            continue;
          }

          const payload = await response.json();
          const data = payload?.data || {};
          if (Array.isArray(data?.items) && data.items.length > 0 && data.items[0]) {
            const item = data.items[0];
            const quote = item.quote || {};
            if (quote && Object.keys(quote).length > 0) {
              return {
                ...quote,
                market: item.market || {},
                url: `https://xueqiu.com/S/${symbol}`,
              };
            }
          }
          if (Array.isArray(data) && data.length > 0 && data[0]) {
            return { ...data[0], url: `https://xueqiu.com/S/${symbol}` };
          }

          const quote = data?.quote || {};
          if (quote && Object.keys(quote).length > 0) {
            return {
              ...quote,
              market: data?.market || {},
              url: `https://xueqiu.com/S/${symbol}`,
            };
          }

          errors.push(`${endpoint} ${candidate} -> empty data`);
        } catch (error) {
          errors.push(`${endpoint} ${candidate} -> ${String(error)}`);
        }
      }
    }

    return { __error: errors.join(' | ') };
  }, { symbolCandidates, endpointCandidates, symbol });
}

async function main() {
  const symbol = (process.argv[2] || '').trim().toUpperCase();
  if (!symbol) {
    usage();
    process.exit(1);
  }

  const wsEndpoint = await resolveWsEndpoint();
  const browser = await chromium.connectOverCDP(wsEndpoint);

  try {
    const page = await getPage(browser);
    await page.goto(`https://xueqiu.com/S/${symbol}`, {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    });
    const result = await fetchQuoteInPage(page, symbol);
    if (!result || result.__error) {
      throw new Error(result?.__error || `Empty Xueqiu quote payload for ${symbol}`);
    }
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(`Error: ${error.message}`);
  process.exit(1);
});
