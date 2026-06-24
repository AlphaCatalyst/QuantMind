import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const runLive = process.env.LIVE_FACTOR_RESEARCH_E2E === '1';
const runFullLive = process.env.LIVE_FACTOR_RESEARCH_FULL_E2E === '1';
const apiBaseURL = (process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

type ApiPayload = Record<string, any>;

function unwrapApiData(payload: ApiPayload): ApiPayload {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data as ApiPayload;
  }
  return payload;
}

async function authenticateLiveUser(page: Page, request: APIRequestContext, label: string) {
  const stamp = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  const username = `${label}${stamp}`;
  const password = 'QuantMindLive123!';
  const tenantId = 'default';

  const registerResponse = await request.post(`${apiBaseURL}/api/v1/auth/register`, {
    data: {
      tenant_id: tenantId,
      username,
      email: `${username}@example.com`,
      password,
      full_name: 'Factor Research Live Browser',
    },
  });
  expect(registerResponse.ok()).toBeTruthy();

  const authPayload = unwrapApiData(await registerResponse.json());
  const token = String(authPayload.access_token || '');
  expect(token).not.toHaveLength(0);

  const storedUser = authPayload.user || {
    id: username,
    username,
    email: `${username}@example.com`,
    tenant_id: tenantId,
  };

  await page.addInitScript(
    ({ accessToken, tenant, user }) => {
      window.localStorage.setItem('access_token', accessToken);
      window.localStorage.setItem('auth_token', accessToken);
      window.localStorage.setItem('refresh_token', '');
      window.localStorage.setItem('tenant_id', tenant);
      window.localStorage.setItem('user', JSON.stringify(user));
    },
    { accessToken: token, tenant: tenantId, user: storedUser },
  );

  return { token, username, tenantId, user: storedUser };
}

function recordApiRequests(page: Page, requestedPaths: string[]) {
  page.on('request', req => {
    const url = new URL(req.url());
    if (url.pathname.startsWith('/api/v1/') || url.pathname.includes('/api/v1/')) {
      requestedPaths.push(`${req.method()} ${url.pathname}`);
    }
  });
  page.on('requestfailed', req => {
    const url = new URL(req.url());
    if (url.pathname.startsWith('/api/v1/') || url.pathname.includes('/api/v1/')) {
      requestedPaths.push(`${req.method()} ${url.pathname} FAILED ${req.failure()?.errorText || ''}`.trim());
    }
  });
}

test.describe('live factor research browser flow', () => {
  test.skip(!runLive, 'set LIVE_FACTOR_RESEARCH_E2E=1 to run against a live QuantMind API');

  test('creates and evaluates a factor candidate through the real API', async ({ page, request }) => {
    test.setTimeout(90000);
    const requestedPaths: string[] = [];

    await authenticateLiveUser(page, request, 'factorui');
    recordApiRequests(page, requestedPaths);

    await page.goto('/#/factor-research');

    await expect(page.getByRole('heading', { name: '因子研究', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: '因子研究是模型训练的前置流水线' })).toBeVisible();
    await expect(page.getByText('因子研究工作台')).toBeVisible();

    const candidateResponsePromise = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && url.pathname === '/api/v1/research/factors/candidates';
    }, { timeout: 60000 });
    const evaluationResponsePromise = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && /^\/api\/v1\/research\/factors\/candidates\/[^/]+\/evaluate$/.test(url.pathname);
    }, { timeout: 60000 });

    await page.getByRole('button', { name: /提交评估/ }).click();

    const candidateResponse = await candidateResponsePromise.catch(error => {
      throw new Error(`candidate POST was not observed. API requests: ${requestedPaths.join(', ') || 'none'}. ${error}`);
    });
    expect(candidateResponse.ok()).toBeTruthy();
    const evaluationResponse = await evaluationResponsePromise.catch(error => {
      throw new Error(`evaluation POST was not observed. API requests: ${requestedPaths.join(', ') || 'none'}. ${error}`);
    });
    expect(evaluationResponse.ok()).toBeTruthy();

    const evaluationPayload = unwrapApiData(await evaluationResponse.json());
    const evaluatedRun = evaluationPayload.run || evaluationPayload;
    expect(evaluatedRun.status).toBe('completed');
    expect(Number(evaluatedRun.metrics?.inserted_values || 0)).toBeGreaterThan(0);

    await page.getByRole('button', { name: /刷新状态/ }).click();
    await expect(page.getByText('最新候选：价格均值偏离')).toBeVisible({ timeout: 15000 });
    await page.getByText('候选因子队列').scrollIntoViewIfNeeded();
    await expect(page.getByRole('row', { name: /价格均值偏离/ }).first()).toBeVisible({ timeout: 15000 });

    await expect
      .poll(() => requestedPaths, { timeout: 5000 })
      .toEqual(expect.arrayContaining([
        'POST /api/v1/research/factors/candidates',
      ]));
    await expect
      .poll(() => requestedPaths, { timeout: 5000 })
      .toEqual(expect.arrayContaining([
        expect.stringMatching(/^POST \/api\/v1\/research\/factors\/candidates\/.+\/evaluate$/),
      ]));
  });

  test('promotes, materializes, and publishes a shadow signal through the real API', async ({ page, request }) => {
    test.skip(!runFullLive, 'set LIVE_FACTOR_RESEARCH_FULL_E2E=1 to run the extended browser acceptance flow');
    test.setTimeout(120000);
    const requestedPaths: string[] = [];

    await authenticateLiveUser(page, request, 'factorfull');
    recordApiRequests(page, requestedPaths);

    await page.goto('/#/factor-research');
    await expect(page.getByRole('heading', { name: '因子研究', exact: true })).toBeVisible();

    const candidateResponsePromise = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && url.pathname === '/api/v1/research/factors/candidates';
    }, { timeout: 60000 });
    const evaluationResponsePromise = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && /^\/api\/v1\/research\/factors\/candidates\/[^/]+\/evaluate$/.test(url.pathname);
    }, { timeout: 60000 });

    await page.getByRole('button', { name: /提交评估/ }).click();
    const candidateResponse = await candidateResponsePromise;
    expect(candidateResponse.ok()).toBeTruthy();
    const evaluationResponse = await evaluationResponsePromise;
    expect(evaluationResponse.ok()).toBeTruthy();

    const evaluationPayload = unwrapApiData(await evaluationResponse.json());
    const evaluatedRun = evaluationPayload.run || evaluationPayload;
    expect(evaluatedRun.status).toBe('completed');
    expect(Number(evaluatedRun.metrics?.inserted_values || 0)).toBeGreaterThan(0);

    await page.getByRole('button', { name: /刷新状态/ }).click();
    await expect(page.getByText('最新候选：价格均值偏离')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Factor Values 预览')).toBeVisible({ timeout: 15000 });

    const promoteResponsePromise = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && /^\/api\/v1\/research\/factors\/candidates\/[^/]+\/promote$/.test(url.pathname);
    }, { timeout: 60000 });
    await page.getByRole('button', { name: /登记 Shadow 特征/ }).click();
    const promoteResponse = await promoteResponsePromise;
    expect(promoteResponse.ok()).toBeTruthy();
    const promotionPayload = unwrapApiData(await promoteResponse.json());
    const promotedFeature = promotionPayload.promotion || promotionPayload;
    expect(String(promotedFeature.featureKey || '')).not.toHaveLength(0);
    const promotedMaterializationStatus = promotedFeature.materializationStatus || promotedFeature.materialization_status;
    if (promotedMaterializationStatus !== 'materialized') {
      const materializeResponsePromise = page.waitForResponse(response => {
        const url = new URL(response.url());
        return response.request().method() === 'POST'
          && /^\/api\/v1\/research\/factors\/promotions\/[^/]+\/materialize$/.test(url.pathname);
      }, { timeout: 60000 });
      await page.getByRole('button', { name: /物化到训练快照/ }).click();
      const materializeResponse = await materializeResponsePromise;
      expect(materializeResponse.ok()).toBeTruthy();
      const materializePayload = unwrapApiData(await materializeResponse.json());
      const materializedPromotion = materializePayload.promotion || materializePayload;
      expect(materializedPromotion.materializationStatus || materializedPromotion.materialization_status).toBe('materialized');
    }
    await expect(page.getByText('可训练', { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('button', { name: /发起 Shadow 训练/ })).toBeEnabled({ timeout: 15000 });

    const signalResponsePromise = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && /^\/api\/v1\/research\/factors\/candidates\/[^/]+\/publish-shadow-signal$/.test(url.pathname);
    }, { timeout: 60000 });
    await page.getByRole('button', { name: /发布 Shadow Signal/ }).click();
    const signalResponse = await signalResponsePromise;
    expect(signalResponse.ok()).toBeTruthy();
    const signalPayload = unwrapApiData(await signalResponse.json());
    const signalRun = signalPayload.signalRun || signalPayload.signal_run || signalPayload;
    expect(Number(signalRun.signalCount || signalRun.signal_count || 0)).toBeGreaterThan(0);
    expect(Number(signalRun.streamPublishedCount || signalRun.stream_published_count || 0)).toBe(0);

    await expect(page.getByText('Shadow Signal 状态')).toBeVisible();
    await expect(page.getByText(/信号数量：[1-9]/)).toBeVisible({ timeout: 15000 });
    const expectedMutationPaths: Array<string | RegExp> = [
      /^POST \/api\/v1\/research\/factors\/candidates\/.+\/promote$/,
      /^POST \/api\/v1\/research\/factors\/candidates\/.+\/publish-shadow-signal$/,
    ];
    if (promotedMaterializationStatus !== 'materialized') {
      expectedMutationPaths.splice(1, 0, /^POST \/api\/v1\/research\/factors\/promotions\/.+\/materialize$/);
    }
    await expect
      .poll(() => requestedPaths, { timeout: 5000 })
      .toEqual(expect.arrayContaining([
        ...expectedMutationPaths.map(pattern => expect.stringMatching(pattern)),
      ]));
  });
});
