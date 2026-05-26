#!/usr/bin/env node
// fetch-marketplace-stats.mjs — daily snapshot of public Marketplace stats.
//
// Run by .github/workflows/marketplace-stats.yml (UC-643).
//
// Privacy: zero PII. The endpoint returns only public aggregate data
// (installs, downloads, ratings, trending ranks).
//
// Endpoint: https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery
// flags=914 = IncludeStatistics (4) + IncludeFiles (2) + IncludeAssetUri (128)
//             + IncludeStatistics+IncludeLatestVersionOnly = bitwise of common flags.
//
// Exit codes:
//   0 = success or "extension not published yet" (soft fail)
//   1 = unexpected error worth investigating

import { appendFileSync, existsSync, readFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const JSONL_PATH = join(REPO_ROOT, '.quality', 'marketplace-stats.jsonl');

const EXTENSION_ID = 'EmbedBuild.specbox-engine';
const ENDPOINT = 'https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery';
const FLAGS = 914;

async function fetchStats() {
    const body = {
        filters: [
            {
                criteria: [{ filterType: 7, value: EXTENSION_ID }],
                pageSize: 1,
                pageNumber: 1,
            },
        ],
        flags: FLAGS,
    };

    const res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: {
            'Accept': 'application/json;api-version=7.2-preview.1;excludeUrls=true',
            'Content-Type': 'application/json',
            'User-Agent': 'specbox-engine-marketplace-stats/1.0',
        },
        body: JSON.stringify(body),
    });

    if (res.status === 404) {
        return { notPublished: true };
    }
    if (!res.ok) {
        throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
    return await res.json();
}

function extractStat(stats, name) {
    if (!Array.isArray(stats)) return 0;
    const entry = stats.find(s => s.statisticName === name);
    return entry ? Number(entry.value) || 0 : 0;
}

function readLastEntry() {
    if (!existsSync(JSONL_PATH)) return null;
    const content = readFileSync(JSONL_PATH, 'utf-8').trim();
    if (!content) return null;
    const lines = content.split('\n').filter(l => l.trim());
    if (lines.length === 0) return null;
    try {
        return JSON.parse(lines[lines.length - 1]);
    } catch {
        return null;
    }
}

async function main() {
    let data;
    try {
        data = await fetchStats();
    } catch (err) {
        console.error(`✗ Failed to query Marketplace: ${err.message}`);
        process.exit(1);
    }

    if (data.notPublished) {
        console.log(`ℹ Extension ${EXTENSION_ID} not yet on Marketplace — soft-skipping.`);
        process.exit(0);
    }

    const extensions = data?.results?.[0]?.extensions || [];
    if (extensions.length === 0) {
        console.log(`ℹ extensionquery returned 0 matches for ${EXTENSION_ID} — soft-skipping.`);
        process.exit(0);
    }

    const ext = extensions[0];
    const stats = ext.statistics || [];
    const version = ext.versions?.[0]?.version || 'unknown';

    const installs = extractStat(stats, 'install');
    const downloads = extractStat(stats, 'updateCount') + installs;  // total grabs
    const avgRating = extractStat(stats, 'averagerating');
    const ratingCount = extractStat(stats, 'ratingcount');
    const trendingDaily = extractStat(stats, 'trendingdaily');
    const trendingWeekly = extractStat(stats, 'trendingweekly');
    const trendingMonthly = extractStat(stats, 'trendingmonthly');

    const last = readLastEntry();
    const deltaInstalls24h = last ? installs - (last.installs || 0) : 0;

    const entry = {
        date: new Date().toISOString(),
        version,
        installs,
        downloads,
        avg_rating: avgRating,
        rating_count: ratingCount,
        trending_daily: trendingDaily,
        trending_weekly: trendingWeekly,
        trending_monthly: trendingMonthly,
        delta_installs_24h: deltaInstalls24h,
    };

    mkdirSync(dirname(JSONL_PATH), { recursive: true });
    appendFileSync(JSONL_PATH, JSON.stringify(entry) + '\n', 'utf-8');

    console.log(`✓ Appended stats entry to ${JSONL_PATH}`);
    console.log(JSON.stringify(entry, null, 2));
}

main().catch(err => {
    console.error(`✗ Unexpected error: ${err.message}`);
    process.exit(1);
});
