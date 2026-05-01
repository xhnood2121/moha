// PM2 process manifest. Two processes:
//   - raqman-web: the Next.js server.
//   - raqman-crawler: the polite public-catalog worker, scheduled hourly.
//
// We deliberately keep the worker count small. Adding more parallel crawlers
// does not help us — the rate limit is per-host, and we will not bypass it.

module.exports = {
  apps: [
    {
      name: "raqman-web",
      cwd: __dirname,
      script: "node_modules/next/dist/bin/next",
      args: "start -p 3000",
      instances: 1,
      autorestart: true,
      max_memory_restart: "1G",
      env: { NODE_ENV: "production" },
    },
    {
      name: "raqman-crawler",
      cwd: __dirname,
      script: "node_modules/.bin/tsx",
      args: "workers/crawl-public.ts",
      autorestart: false,
      cron_restart: "15 * * * *",
      env: { NODE_ENV: "production" },
    },
  ],
};
