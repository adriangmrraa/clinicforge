import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import axios from 'axios';
import path from 'path';
import http from 'http';
import { createProxyMiddleware } from 'http-proxy-middleware';

// Buscar .env en la carpeta actual o en la raíz
dotenv.config();
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const app = express();
const port = process.env.PORT || 3000;

// Mejor fallback para desarrollo local
const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_SERVICE_URL ||
    process.env.ORCHESTRATOR_URL ||
    'http://localhost:8000';

// --- S-8/F-3: ADMIN_TOKEN server-side injection ---
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || '';
if (!ADMIN_TOKEN || ADMIN_TOKEN.length < 32) {
    console.error(
        'CRITICAL: ADMIN_TOKEN is not set or is shorter than 32 characters. ' +
        'The BFF cannot inject admin tokens. Exiting.'
    );
    process.exit(1);
}

// --- S-1: CORS allowlist from env ---
const rawOrigins = process.env.ALLOWED_ORIGINS || '';
const allowedOrigins: string[] = rawOrigins
    .split(',')
    .map(o => o.trim())
    .filter(o => {
        if (!o) return false;
        try {
            new URL(o);
            return true;
        } catch {
            console.warn(`WARNING: Skipping malformed CORS origin: ${o}`);
            return false;
        }
    });

if (allowedOrigins.length === 0) {
    console.warn('WARNING: ALLOWED_ORIGINS is not set — all cross-origin requests will be rejected');
}

app.use(cors({
    origin: (origin, callback) => {
        // Allow same-origin requests (no Origin header) and server-to-server
        if (!origin) return callback(null, true);
        if (allowedOrigins.includes(origin)) return callback(null, true);
        console.warn(`CORS rejected origin: ${origin}`);
        callback(new Error(`Origin ${origin} not allowed by CORS`));
    },
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
    allowedHeaders: ['Content-Type', 'Authorization', 'x-tenant-id', 'x-signature']
}));

// Skip express.json() for multipart requests (preserve raw stream for file uploads)
app.use((req: Request, res: Response, next: NextFunction) => {
    const ct = req.headers['content-type'] || '';
    if (ct.includes('multipart/')) return next();
    express.json({ limit: '10mb' })(req, res, next);
});

// --- Socket.IO WebSocket proxy (BEFORE body parsers) ---
app.use('/socket.io', createProxyMiddleware({
    target: ORCHESTRATOR_URL,
    ws: true,
    changeOrigin: true,
    logger: console,
}));

// Root Route
app.get('/', (req: Request, res: Response) => {
    res.send('BFF Service is Running');
});

// Health Check
app.get('/health', (req: Request, res: Response) => {
    console.log('[Health] Check received');
    res.json({ status: 'ok', service: 'bff-interface', mode: 'proxy' });
});

// Proxy Middleware (Catch-all)
app.use(async (req: Request, res: Response) => {
    const url = `${ORCHESTRATOR_URL}${req.originalUrl}`;
    console.log(`[Proxy] Forwarding ${req.method} ${req.originalUrl} -> ${url}`);

    // Filtrar headers problemáticos
    const headers = { ...req.headers };
    delete headers.host;
    delete headers['content-length'];
    delete headers.connection;

    // F-3: Strip any incoming x-admin-token (prevent client spoofing)
    // and inject the server-side token
    delete headers['x-admin-token'];
    headers['x-admin-token'] = ADMIN_TOKEN;

    // Multipart (file uploads): pipe raw stream via http.request
    const contentType = req.headers['content-type'] || '';
    if (contentType.includes('multipart/')) {
        try {
            const parsedUrl = new URL(url);
            const proxyReq = http.request({
                hostname: parsedUrl.hostname,
                port: parsedUrl.port,
                path: parsedUrl.pathname + parsedUrl.search,
                method: req.method,
                headers: {
                    ...headers,
                    'content-type': contentType,
                    ...(req.headers['content-length'] ? { 'content-length': req.headers['content-length'] } : {}),
                },
                timeout: 120000,
            }, (proxyRes) => {
                res.status(proxyRes.statusCode || 502);
                if (proxyRes.headers['content-type']) {
                    res.setHeader('Content-Type', proxyRes.headers['content-type']);
                }
                proxyRes.pipe(res);
            });
            proxyReq.on('error', (err) => {
                console.error(`[Proxy Error] multipart: ${err.message}`);
                res.status(502).json({ error: 'Orchestrator unavailable', details: err.message });
            });
            req.pipe(proxyReq);
        } catch (err: any) {
            console.error(`[Proxy Error] multipart setup: ${err.message}`);
            res.status(502).json({ error: 'Proxy error', details: err.message });
        }
        return;
    }

    // JSON / standard requests: use axios
    try {
        const response = await axios({
            method: req.method,
            url: url,
            data: req.body,
            headers: headers,
            timeout: 120000,
            validateStatus: () => true
        });

        if (response.headers['content-type']) {
            res.setHeader('Content-Type', response.headers['content-type']);
        }

        res.status(response.status).send(response.data);
    } catch (error: any) {
        console.error(`[Proxy Error] ${error.message}`);
        if (error.response) {
            res.status(error.response.status).send(error.response.data);
        } else {
            res.status(502).json({
                error: 'Orchestrator unavailable',
                details: error.message,
                target: url
            });
        }
    }
});

const server = app.listen(port, () => {
    console.log(`BFF Service running on port ${port}`);
    console.log(`Proxying to Orchestrator at: ${ORCHESTRATOR_URL}`);
    console.log(`Socket.IO WebSocket proxy enabled on /socket.io`);
    console.log(`CORS allowed origins: ${allowedOrigins.length > 0 ? allowedOrigins.join(', ') : '(none — rejecting all cross-origin)'}`);
});
