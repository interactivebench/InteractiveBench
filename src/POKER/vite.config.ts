import fs from 'fs';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const NUM_TABLES = 10;

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');

    // Create log file paths for each table
    const getLogFile = (tableId: number) => path.resolve(__dirname, `game-log-${tableId}.ndjson`);
    const getStatsFile = (tableId: number) => path.resolve(__dirname, `stats-log-${tableId}.ndjson`);

    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
      },
      plugins: [
        react(),
        {
          name: 'poker-log-writer',
          configureServer(server) {
            // Handle table-specific log endpoints: /__pokerlog/1 through /__pokerlog/10
            for (let tableId = 1; tableId <= NUM_TABLES; tableId++) {
              const endpoint = `/__pokerlog/${tableId}`;
              const logFile = getLogFile(tableId);

              server.middlewares.use(endpoint, (req, res, next) => {
                if (req.method !== 'POST') return next();
                let body = '';
                req.on('data', (chunk) => { body += chunk; });
                req.on('end', () => {
                  try {
                    const line = body.trim();
                    if (line) fs.appendFileSync(logFile, line + '\n', 'utf8');
                    res.statusCode = 200;
                    res.end('ok');
                  } catch (err) {
                    console.error(`[poker-log-writer] Table ${tableId}:`, err);
                    res.statusCode = 500;
                    res.end('error');
                  }
                });
              });
            }

            // Legacy endpoint for backwards compatibility (writes to game-log-0.ndjson)
            server.middlewares.use('/__pokerlog', (req, res, next) => {
              // Skip if it's a table-specific endpoint (already handled above)
              if (req.url && req.url.match(/^\/\d+/)) return next();
              if (req.method !== 'POST') return next();
              let body = '';
              req.on('data', (chunk) => { body += chunk; });
              req.on('end', () => {
                try {
                  const line = body.trim();
                  const logFile = path.resolve(__dirname, 'game-log-0.ndjson');
                  if (line) fs.appendFileSync(logFile, line + '\n', 'utf8');
                  res.statusCode = 200;
                  res.end('ok');
                } catch (err) {
                  console.error('[poker-log-writer] Legacy:', err);
                  res.statusCode = 500;
                  res.end('error');
                }
              });
            });

            // Stats log endpoints: /__pokerstats/1 through /__pokerstats/10
            // These record player stats over time for each table
            for (let tableId = 1; tableId <= NUM_TABLES; tableId++) {
              const endpoint = `/__pokerstats/${tableId}`;
              const statsFile = getStatsFile(tableId);

              server.middlewares.use(endpoint, (req, res, next) => {
                if (req.method !== 'POST') return next();
                let body = '';
                req.on('data', (chunk) => { body += chunk; });
                req.on('end', () => {
                  try {
                    const line = body.trim();
                    if (line) fs.appendFileSync(statsFile, line + '\n', 'utf8');
                    res.statusCode = 200;
                    res.end('ok');
                  } catch (err) {
                    console.error(`[stats-log-writer] Table ${tableId}:`, err);
                    res.statusCode = 500;
                    res.end('error');
                  }
                });
              });
            }
          }
        }
      ],
      define: {
        'process.env.OPENROUTER_POKER_API': JSON.stringify(env.OPENROUTER_POKER_API || env.OPENROUTER_API_KEY || ''),
        'process.env.OPENROUTER_API_KEY': JSON.stringify(env.OPENROUTER_POKER_API || env.OPENROUTER_API_KEY || '')
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      }
    };
});
