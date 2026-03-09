import express, { Request, Response } from 'express';
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

app.use(cors({
    origin: true,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
    allowedHeaders: ['Content-Type', 'Authorization', 'x-admin-token', 'x-tenant-id', 'x-signature']
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

    try {
        const response = await axios({
            method: req.method,
            url: url,
            data: ['POST', 'PUT', 'PATCH'].includes(req.method) ? req.body : undefined,
            headers: headers,
            validateStatus: () => true // Permitir que axios devuelva cualquier status para reenviarlo
        });

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
});
