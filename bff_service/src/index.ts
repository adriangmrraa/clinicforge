import express, { Request, Response } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import axios from 'axios';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;
const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_SERVICE_URL || process.env.ORCHESTRATOR_URL || 'http://orchestrator_service:8000';

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

    try {
        const response = await axios({
            method: req.method,
            url: url,
            data: req.body,
            headers: { ...req.headers, host: undefined }
        });
        res.status(response.status).send(response.data);
    } catch (error: any) {
        console.error(`[Proxy Error] ${error.message}`);
        if (error.response) {
            res.status(error.response.status).send(error.response.data);
        } else {
            res.status(502).json({ error: 'Orchestrator unavailable', details: error.message });
        }
    }
});

app.listen(port, () => {
    console.log(`BFF Service running on port ${port}`);
    console.log(`Proxying to Orchestrator at: ${ORCHESTRATOR_URL}`);
});