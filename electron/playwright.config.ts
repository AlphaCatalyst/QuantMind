import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.PLAYWRIGHT_PORT || process.env.VITE_PORT || 3100);
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${port}`;
const apiBaseURL = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Playwright配置文件
 * 用于端到端测试配置
 */
export default defineConfig({
  // 测试目录
  testDir: './tests/e2e',

  // 测试超时时间
  timeout: 30000,

  // 期望超时时间
  expect: {
    timeout: 5000,
  },

  // 失败时重试次数
  retries: process.env.CI ? 2 : 0,

  // 并发工作进程
  workers: process.env.CI ? 1 : undefined,

  // 测试报告
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results.json' }],
    ['list'],
  ],

  // 全局配置
  use: {
    // 基础URL
    baseURL,

    // 追踪配置
    trace: 'on-first-retry',

    // 截图配置
    screenshot: 'only-on-failure',

    // 视频配置
    video: 'retain-on-failure',

    // 浏览器上下文
    contextOptions: {
      ignoreHTTPSErrors: true,
    },
  },

  // 测试项目配置
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    // 可选的其他浏览器
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },

    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },

    // 移动端测试
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
  ],

  // Web服务器配置
  webServer: {
    command: `npx cross-env VITE_PORT=${port} VITE_API_BASE_URL=${apiBaseURL} VITE_DISABLE_AUTH=true npm run dev:react -- --host 127.0.0.1`,
    port,
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.CI,
  },
});
