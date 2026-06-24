import { expect, test } from '@playwright/test';

const now = '2026-06-24T09:00:00.000Z';

const user = {
  id: 59427183,
  username: 'model-training-factor-e2e',
  email: 'model-training-factor-e2e@example.com',
  full_name: 'Model Training Factor E2E',
  tenant_id: 'default',
  is_active: true,
  is_admin: true,
  created_at: now,
  updated_at: now,
};

const accessToken = [
  Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64'),
  Buffer.from(JSON.stringify({ sub: String(user.id), exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64'),
  'signature',
].join('.');

const featureCatalog = {
  version_id: 'factor_shadow_feature_set_e2e',
  version_name: '因子研究 Shadow Feature Set',
  feature_count: 2,
  source: 'database',
  categories: [
    {
      id: 'factor_research',
      name: '因子研究晋升特征',
      order: 1,
      feature_count: 1,
      features: [
        {
          feature_id: 'factor_alpha',
          key: 'factor_alpha',
          feature_name: 'Alpha 价格均值偏离',
          formula: 'rank(close / ts_mean(close, 20))',
          source_table_fields: 'qm_factor_values.factor_value',
          enabled: true,
          order_no: 1,
        },
      ],
    },
    {
      id: 'momentum',
      name: '动量',
      order: 2,
      feature_count: 1,
      features: [
        {
          feature_id: 'mom_ret_5d',
          key: 'mom_ret_5d',
          feature_name: '5日收益率动量',
          formula: 'ret_5d',
          source_table_fields: 'model_features.mom_ret_5d',
          enabled: true,
          order_no: 1,
        },
      ],
    },
  ],
  data_coverage: {
    source: 'feature_snapshots',
    snapshot_dir: 'db/feature_snapshots',
    file_count: 1,
    scanned_files: 1,
    failed_files: 0,
    total_rows: 100,
    min_date: '2026-01-01',
    max_date: '2026-06-24',
    suggested_periods: {
      train: ['2026-01-01', '2026-03-31'],
      val: ['2026-04-01', '2026-05-15'],
      test: ['2026-05-16', '2026-06-24'],
    },
  },
};

test('model training consumes factor research feature catalog entries', async ({ page }) => {
  const requestedPaths: string[] = [];

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    requestedPaths.push(`${request.method()} ${path}`);

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/models/feature-catalog')) {
      await route.fulfill({ json: featureCatalog });
      return;
    }

    await route.fulfill({ json: {} });
  });

  await page.goto('/#/model-training');

  await expect(page.getByText('上游：因子研究')).toBeVisible();
  await expect(page.getByText('通过门禁后再进入训练特征集')).toBeVisible();
  await expect(page.getByText('第一步：选择特征维度')).toBeVisible();
  await expect(page.getByText('因子研究晋升特征')).toBeVisible();
  await page.getByRole('button', { name: /因子研究晋升特征/ }).click();
  await expect(page.getByText('Alpha 价格均值偏离')).toBeVisible();
  await expect(page.getByText('1 个候选特征 · 已选 0 项')).toBeVisible();
  expect(requestedPaths).toContain('GET /api/v1/models/feature-catalog');
});
