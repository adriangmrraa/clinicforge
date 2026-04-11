import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import axios from 'axios';
import path from 'path';
import { createProxyMiddleware } from 'http-proxy-middleware';
import rateLimit from 'express-rate-limit';

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

// --- Rate Limiting ---
const globalLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 200,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests' }
});

const authLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 10,
    message: { error: 'Too many auth requests' }
});

app.use(globalLimiter);
app.use('/auth', authLimiter);

// Body parsers: JSON for normal requests, raw buffer for multipart (file uploads)
app.use((req: Request, res: Response, next: NextFunction) => {
    const ct = req.headers['content-type'] || '';
    if (ct.includes('multipart/')) {
        // Buffer the raw multipart body so we can forward it via axios
        const MAX_MULTIPART_SIZE = 100 * 1024 * 1024; // 100MB
        const chunks: Buffer[] = [];
        let totalSize = 0;
        req.on('data', (chunk: Buffer) => {
            totalSize += chunk.length;
            if (totalSize > MAX_MULTIPART_SIZE) {
                res.status(413).json({ error: 'Payload too large (max 100MB)' });
                req.destroy();
                return;
            }
            chunks.push(chunk);
        });
        req.on('end', () => {
            (req as any).rawBody = Buffer.concat(chunks);
            next();
        });
        req.on('error', (err) => {
            console.error('[Body Parser] multipart read error:', err.message);
            next(err);
        });
    } else {
        express.json({ limit: '10mb' })(req, res, next);
    }
});

// --- Socket.IO WebSocket proxy (BEFORE catch-all) ---
app.use('/socket.io', createProxyMiddleware({
    target: ORCHESTRATOR_URL,
    ws: true,
    changeOrigin: true,
    logger: console,
}));

// --- Nova WebSocket proxy (voice + realtime text) ---
app.use('/public/nova', createProxyMiddleware({
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
    const isMediaRoute = req.originalUrl.includes('/media/proxy') || /\/documents\/\d+\/proxy/.test(req.originalUrl);
    console.log(`[Proxy] Forwarding ${req.method} ${req.originalUrl} -> ${url}${isMediaRoute ? ' [BINARY]' : ''}`);

    // Filtrar headers problemáticos
    const headers = { ...req.headers };
    delete headers.host;
    delete headers['content-length'];
    delete headers.connection;

    // F-3: Strip any incoming x-admin-token (prevent client spoofing)
    // and inject the server-side token
    delete headers['x-admin-token'];
    headers['x-admin-token'] = ADMIN_TOKEN;

    const contentType = req.headers['content-type'] || '';
    const isMultipart = contentType.includes('multipart/');

    if (isMultipart) {
        const rawBody = (req as any).rawBody;
        console.log(`[Proxy] Multipart upload: ${rawBody ? rawBody.length : 0} bytes`);
    }

    // Detect if this request expects a binary response (PDF, images, media proxy, etc.)
    const acceptHeader = (req.headers['accept'] || '').toLowerCase();
    const isPdfRequest = req.originalUrl.endsWith('/pdf') || req.originalUrl.includes('/generate-pdf') || acceptHeader.includes('application/pdf');
    const isMediaProxy = /\/documents\/\d+\/proxy/.test(req.originalUrl)
        || req.originalUrl.includes('/chat/media/proxy')
        || req.originalUrl.includes('/uploads/')
        || req.originalUrl.includes('/media/')
        || req.originalUrl.includes('/tenant-logo/');
    const isBinaryRequest = isPdfRequest || isMediaProxy || acceptHeader.includes('application/octet-stream');

    try {
        const response = await axios({
            method: req.method,
            url: url,
            // For multipart: send raw buffer with original content-type (includes boundary)
            // For JSON: send parsed body
            data: isMultipart ? (req as any).rawBody : req.body,
            headers: isMultipart
                ? { ...headers, 'content-type': contentType, 'content-length': String((req as any).rawBody?.length || 0) }
                : headers,
            timeout: 120000,
            maxContentLength: Infinity,
            maxBodyLength: Infinity,
            // Binary responses need arraybuffer to avoid corruption
            responseType: isBinaryRequest ? 'arraybuffer' : undefined,
            // Don't let axios transform the multipart buffer
            ...(isMultipart ? { transformRequest: [(data: any) => data] } : {}),
            validateStatus: () => true
        });

        // Forward all response headers
        if (response.headers['content-type']) {
            res.setHeader('Content-Type', response.headers['content-type']);
        }
        if (response.headers['content-disposition']) {
            res.setHeader('Content-Disposition', response.headers['content-disposition']);
        }

        if (isBinaryRequest) {
            const size = response.data?.byteLength || response.data?.length || 0;
            console.log(`[Proxy] Binary response: status=${response.status} type=${response.headers['content-type']} size=${size} bytes`);
        }

        res.status(response.status).send(response.data);
    } catch (error: any) {
        console.error(`[Proxy Error] ${req.method} ${req.path}: ${error.message}`);
        if (error.response) {
            res.status(error.response.status).send(error.response.data);
        } else {
            res.status(502).json({ error: 'Service temporarily unavailable' });
        }
    }
});

const server = app.listen(port, () => {
    console.log(`BFF Service running on port ${port}`);
    console.log(`Proxying to Orchestrator at: ${ORCHESTRATOR_URL}`);
    console.log(`Socket.IO WebSocket proxy enabled on /socket.io`);
    console.log(`CORS allowed origins: ${allowedOrigins.length > 0 ? allowedOrigins.join(', ') : '(none — rejecting all cross-origin)'}`);
});
