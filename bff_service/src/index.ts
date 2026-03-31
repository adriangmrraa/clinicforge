import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import axios from 'axios';
import path from 'path';

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

app.options('*', cors());
app.use(express.json());

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

    try {
        const response = await axios({
            method: req.method,
            url: url,
            data: req.body,
            headers: headers,
            timeout: 60000, // Extend timeout for complex LLM tasks
            validateStatus: () => true
        });

        // Reenviar headers de respuesta importantes
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

app.listen(port, () => {
    console.log(`BFF Service running on port ${port}`);
    console.log(`Proxying to Orchestrator at: ${ORCHESTRATOR_URL}`);
    console.log(`CORS allowed origins: ${allowedOrigins.length > 0 ? allowedOrigins.join(', ') : '(none — rejecting all cross-origin)'}`);
});
