// @ts-check
const { test, expect } = require('@playwright/test');

async function waitForDataLoaded(page) {
  await page.waitForFunction(() => {
    return window.__contabulateReady === true;
  }, { timeout: 15000 });
}

async function pickSampleQuery(page) {
  return 'whale';
}

async function search(page, query, { gran = 'play', ngramMode = '1', matchMode = 'exact' } = {}) {
  await page.selectOption('#gran', gran);
  await page.selectOption('#matchMode', matchMode);
  if (matchMode === 'regex') {
    await page.selectOption('#ngramMode', ngramMode);
  }
  await page.fill('#q', query);
  await page.press('#q', 'Enter');
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  if (gran === 'line') {
    await expect(page.locator('#results thead')).toContainText('Paragraph', { timeout: 10000 });
  }
}

test.describe('Page Load', () => {
  test('loads and shows the Melville title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Melville/);
  });

  test('shows base stats on first load with no search terms', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    await page.waitForSelector('#results tbody tr', { timeout: 10000 });
    await expect(page.locator('#results tbody tr')).toHaveCount(11);
    const texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Location'))).toBeTruthy();
    expect(texts.some(t => t.includes('Work'))).toBeTruthy();
    expect(texts.some(t => t.includes('Year'))).toBeTruthy();
    expect(texts.some(t => t.includes('# words'))).toBeTruthy();
    expect(texts.some(t => t.includes('# paragraphs'))).toBeTruthy();
    // No commentary data in this corpus: the columns must not appear
    expect(texts.some(t => t.includes('# comments'))).toBeFalsy();
    expect(texts.some(t => t.includes('Comments /'))).toBeFalsy();
  });
});

test.describe('Segments Search', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
  });

  test('supports exact-term auto ngram detection and removable headers', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await page.fill('#q', `${sample} ${sample}`);
    await page.click('#addColumnBtn');
    await expect(page.locator('#results thead th')).toContainText([`"${sample} ${sample}"`]);
    await page.locator('#results thead th button.term-col-remove').click();
    await expect(page.locator('#results thead th')).not.toContainText([`"${sample} ${sample}"`]);
  });

  test('the + popover offers metrics only, without a commentators group', async ({ page }) => {
    await page.locator('#results thead th.add-column-th').click();
    const popover = page.locator('.add-column-popover');
    await expect(popover).toBeVisible();
    await expect(popover.locator('.add-column-search')).toHaveAttribute('placeholder', 'Search metrics...');
    await expect(popover.locator('.add-column-group-title', { hasText: 'Commentators' })).toHaveCount(0);
    await popover.locator('.add-column-option', { hasText: '% Hapax' }).click();
    await page.keyboard.press('Escape');
    const texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('% Hapax'))).toBeTruthy();
  });

  test('count cells drill down and ancestor cells filter', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    // Works → the 34 chapters of Typee
    await page.locator('#results tbody tr').first().locator('td:nth-child(5) button.drill-link').click();
    await expect(page.locator('#gran')).toHaveValue('act');
    await expect(page.locator('#segmentsTotalInfo')).toContainText('(34 total rows)');
    await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 01.TYPE.');
    // Back un-drills
    await page.goBack();
    await expect(page.locator('#gran')).toHaveValue('play');
    // Genre cell filters works to that genre
    await page.locator('#results tbody tr').first().locator('td:nth-child(4) .drill-link').click();
    await expect(page.locator('#results tbody tr')).toHaveCount(9);
    await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('is Novel');
  });

  test('vocabulary granularities put n-grams in the rows', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    await page.selectOption('#gran', 'word');
    await expect(page.locator('#results thead th[data-key="ngram"]')).toHaveCount(1);
    await expect(page.locator('#results thead th[data-key="unusualness"]')).toHaveCount(1);
    // No proper-name data in this corpus, so the toggle stays hidden
    await expect(page.locator('#vocabNamesToggle')).toBeHidden();
    // The search box filters the Word column here
    await page.fill('#q', 'whale');
    await page.locator('#addColumnBtn').click();
    await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('matches whale');
    const words = await page.locator('#results tbody tr td:first-child').allTextContents();
    expect(words.length).toBeGreaterThan(0);
    expect(words.every(w => w.includes('whale'))).toBeTruthy();
  });

  test('supports regex mode with explicit ngram selection', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, `^${sample}$`, { gran: 'play', matchMode: 'regex', ngramMode: '1' });
    expect(await page.locator('#results tbody tr').count()).toBeGreaterThan(0);
  });

  test('paragraph rows render highlights', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'line' });
    await page.locator('#segmentsTab details summary').click();
    await expect(page.locator('#results tbody td .hit').first()).toBeVisible({ timeout: 10000 });
  });

  test('granularity selector uses Paragraph for paragraph text rows', async ({ page }) => {
    const options = await page.locator('#gran option').evaluateAll((opts) =>
      opts.map((opt) => ({ value: opt.value, text: (opt.textContent || '').trim() }))
    );
    expect(options.some((opt) => opt.value === 'scene')).toBeFalsy();
    expect(options).toContainEqual({ value: 'line', text: 'Paragraph' });
  });

  test('maps legacy paragraph URL granularities to text-backed Paragraph view', async ({ page }) => {
    const sample = await pickSampleQuery(page);
    await page.goto(`/?q=${sample}&nm=1&gran=line&mm=exact&sk=location&sd=asc&cs=1&zr=0&hl=1`);
    await waitForDataLoaded(page);
    await page.waitForSelector('#results tbody tr', { timeout: 10000 });
    await expect(page.locator('#gran')).toHaveValue('line');
    let texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Paragraph'))).toBeTruthy();

    await page.goto(`/?q=${sample}&nm=1&gran=scene&mm=exact&sk=location&sd=asc&cs=1&zr=0&hl=1`);
    await waitForDataLoaded(page);
    await page.waitForSelector('#results tbody tr', { timeout: 10000 });
    await expect(page.locator('#gran')).toHaveValue('line');
    texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Paragraph'))).toBeTruthy();
  });
});

test.describe('Paragraphs View', () => {
  test('shows matching paragraph rows at Paragraph granularity', async ({ page }) => {
    await page.goto('/');
    await waitForDataLoaded(page);
    const sample = await pickSampleQuery(page);
    await search(page, sample, { gran: 'line' });
    const texts = await page.locator('#results thead th').allTextContents();
    expect(texts.some(t => t.includes('Work'))).toBeTruthy();
    expect(texts.some(t => t.includes('Chapter'))).toBeTruthy();
    expect(texts.some(t => t.includes('Paragraph #'))).toBeTruthy();
    expect(texts.some(t => t.includes('# comments'))).toBeFalsy();
    await expect(page.locator('#results tbody tr').first()).toBeVisible();
  });
});

test('vocabulary scope survives switching the n-gram size', async ({ page }) => {
  await page.goto('/?gran=word&s_ft_location=%5E06%5C.MD%5C.');
  await waitForDataLoaded(page);
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 06.MD.');
  // Switching word -> bigram keeps the same scope in place
  await page.selectOption('#gran', 'bigram');
  await page.waitForSelector('#results tbody tr', { timeout: 10000 });
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 06.MD.');
  await page.selectOption('#gran', 'trigram');
  await expect(page.locator('#segmentsActiveFilters .active-filter-chip')).toContainText('starts with 06.MD.');
});
