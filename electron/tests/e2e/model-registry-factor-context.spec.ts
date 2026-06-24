import { expect, test } from '@playwright/test';

const now = '2026-06-24T09:00:00.000Z';

const user = {
  id: 59427183,
  username: 'model-registry-e2e',
  email: 'model-registry-e2e@example.com',
  full_name: 'Model Registry E2E',
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

const factorModel = {
  tenant_id: 'default',
  user_id: String(user.id),
  model_id: 'model_train_e2e',
  source_run_id: 'train-e2e',
  status: 'ready',
  storage_path: '/tmp/model_train_e2e',
  model_file: 'model.lgb',
  is_default: true,
  created_at: now,
  updated_at: now,
  activated_at: now,
  metrics_json: {
    test_auc: 0.58,
  },
  metadata_json: {
    display_name: '因子研究 Shadow 训练 - factor_alpha',
    model_name: '因子研究 Shadow 训练 - factor_alpha',
    source_pipeline: 'factor_shadow_training',
    promoted_factor_key: 'factor_alpha',
    promoted_factor_expression: 'rank(close / mean(close, 20))',
    feature_set_version_id: 'feature-set-e2e',
    factor_research: {
      promotion_id: 'promotion-e2e',
      candidate_id: 'candidate-e2e',
      factor_run_id: 'run-e2e',
      feature_key: 'factor_alpha',
      feature_set_version_id: 'feature-set-e2e',
      expression: 'rank(close / mean(close, 20))',
      pipeline_stage: 'factor_shadow_training',
      includes_promoted_factor: true,
      baseline_training_run_id: 'baseline-train-e2e',
    },
  },
};

test('model registry attribution shows factor research source metadata', async ({ page }) => {
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

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/models') && request.method() === 'GET') {
      await route.fulfill({ json: { items: [factorModel], total: 1 } });
      return;
    }

    if (path.endsWith('/models/feature-catalog')) {
      await route.fulfill({ json: { categories: [] } });
      return;
    }

    if (path.endsWith('/models/model_train_e2e/shap-summary')) {
      await route.fulfill({
        json: {
          model_id: 'model_train_e2e',
          status: 'completed',
          split: 'valid',
          rows_requested: 30000,
          rows_used: 1200,
          file: 'shap_summary.csv',
          file_exists: true,
          total: 1,
          items: [
            {
              rank: 1,
              feature: 'factor_alpha',
              mean_abs_shap: 0.42,
              mean_shap: 0.12,
              positive_ratio: 0.67,
            },
          ],
        },
      });
      return;
    }

    await route.fulfill({ json: {} });
  });

  await page.goto('/#/model-registry');

  await expect(page.getByText('因子研究 Shadow 训练 - factor_alpha').first()).toBeVisible();
  await page.getByRole('tab', { name: /归因分析/ }).click();

  await expect(page.getByText('因子研究来源')).toBeVisible();
  await expect(page.getByText('factor_shadow_training')).toBeVisible();
  await expect(page.getByText('factor_alpha').first()).toBeVisible();
  await expect(page.getByText('rank(close / mean(close, 20))')).toBeVisible();
  await expect(page.getByText('feature-set-e2e')).toBeVisible();
  await expect(page.getByText('baseline-train-e2e')).toBeVisible();
});
