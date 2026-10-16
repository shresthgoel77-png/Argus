import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const envPath = path.resolve(__dirname, '.env');
if (fs.existsSync(envPath)) {
    for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
        const match = line.match(/^\s*([^#=]+)\s*=\s*(.*)\s*$/);
        if (match && !process.env[match[1]]) {
            process.env[match[1]] = match[2].replace(/^["']|["']$/g, '');
        }
    }
}

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    use: {
        baseURL: 'http://localhost:3000',
        trace: 'on-first-retry',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
    webServer: [
        {
            command: 'cd ../backend && .\\venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000',
            url: 'http://localhost:8000/api/v1/health',
            reuseExistingServer: true,
            timeout: 120000,
        },
        {
            command: 'npm run dev',
            url: 'http://localhost:3000',
            reuseExistingServer: true,
            timeout: 120000,
        }
    ],
});
