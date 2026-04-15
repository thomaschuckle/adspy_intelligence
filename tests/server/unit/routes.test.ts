// tests/server/routes.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import request from 'supertest';
import express, { Express } from 'express';
import { registerRoutes } from '../../../server/routes';
import { lambdaService } from '../../../server/services/lambda';
import type { AdImageReturn } from '../../../server/services/lambda';

// -----------------------------
// Mock lambdaService methods
// -----------------------------
vi.mock('../../../server/services/lambda', async () => {
  const actual: any = await vi.importActual('../../../server/services/lambda');
  return {
    ...actual,
    lambdaService: {
      getJobId: vi.fn(),
      triggerScrapperStatus: vi.fn(),
      getCompanyImages: vi.fn(),
      triggerReportStatus: vi.fn(),
      getCompanyReport: vi.fn()
    }
  };
});

let app: Express;

beforeEach(async () => {
  app = express();
  app.use(express.json());
  await registerRoutes(app);
});

describe('Routes integration tests', () => {

  // -----------------------------
  // 1. Missing or invalid companyName/sessionUuid -> 400
  // -----------------------------
  it('POST /api/get-jobId - invalid body should return 400', async () => {
    const res = await request(app).post('/api/get-jobId').send({ invalid: 'data' });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });

  // -----------------------------
  // 2. Successful jobId retrieval -> 200
  // -----------------------------
  it('POST /api/get-jobId - valid request returns jobId', async () => {
    (lambdaService.getJobId as any).mockResolvedValue({ jobId: 'job-123', success: true });

    const res = await request(app)
      .post('/api/get-jobId')
      .send({ companyName: 'TestCo', sessionUuid: 'uuid-123' });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ jobId: 'job-123' });
  });

  // -----------------------------
  // 3. Lambda scraping failure -> 500
  // -----------------------------
  it('POST /api/scrape-data - Lambda scraping failed', async () => {
    (lambdaService.triggerScrapperStatus as any).mockResolvedValue({ failed: true, completed: false, message: 'Error' });

    const res = await request(app)
      .post('/api/scrape-data')
      .send({ companyName: 'TestCo', jobId: 'job-123' });

    expect(res.status).toBe(500);
    expect(res.body).toHaveProperty('message', 'Lambda scraping failed: Error');
  });

  // -----------------------------
  // 4. Lambda scraping timeout -> 408
  // -----------------------------
  it('POST /api/scrape-data - scraping timed out', async () => {
    (lambdaService.triggerScrapperStatus as any).mockResolvedValue({ failed: false, completed: false, message: 'Timeout' });

    const res = await request(app)
      .post('/api/scrape-data')
      .send({ companyName: 'TestCo', jobId: 'job-123' });

    expect(res.status).toBe(408);
    expect(res.body).toHaveProperty('message', 'Lambda scraping timed out: Timeout');
  });

  // -----------------------------
  // 5. Successful scraping -> 200
  // -----------------------------
  it('POST /api/scrape-data - successful scraping returns images', async () => {
    const mockImages: AdImageReturn[] = [
      { id: 'ad_0', url: 'url1', thumbnail: 'url1', caption: 'TestCo - Image 1', adNumber: 0, companyName: 'TestCo', campaignId: 'camp1', creativeId: 'cre1' }
    ];

    (lambdaService.triggerScrapperStatus as any).mockResolvedValue({ failed: false, completed: true, message: 'Success' });
    (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

    const res = await request(app)
      .post('/api/scrape-data')
      .send({ companyName: 'TestCo', jobId: 'job-123' });

    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('images');
    expect(res.body.images).toHaveLength(1);
    expect(res.body.images[0].id).toBe('ad_0');
  });

  // -----------------------------
  // 6. Report polling failure -> 500
  // -----------------------------
  it('POST /api/poll-report - report generation failed', async () => {
    (lambdaService.triggerReportStatus as any).mockResolvedValue({ failed: true, completed: false, message: 'Report Error' });

    const res = await request(app)
      .post('/api/poll-report')
      .send({ companyName: 'TestCo', jobId: 'job-123' });

    expect(res.status).toBe(500);
    expect(res.body.message).toBe('Lambda report generation failed: Report Error');
  });

  // -----------------------------
  // 7. Report not found -> 404
  // -----------------------------
  it('POST /api/get-report - report not found', async () => {
    (lambdaService.getCompanyReport as any).mockResolvedValue(null);

    const res = await request(app)
      .post('/api/get-report')
      .send({ companyName: 'TestCo', jobId: 'job-123' });

    expect(res.status).toBe(404);
    expect(res.body).toHaveProperty('message');
  });

  // -----------------------------
  // 8. Successful report retrieval -> 200
  // -----------------------------
  it('POST /api/get-report - returns report', async () => {
    const mockReport = { overview: 'Report overview', companyName: 'TestCo' };
    (lambdaService.getCompanyReport as any).mockResolvedValue(mockReport);

    const res = await request(app)
      .post('/api/get-report')
      .send({ companyName: 'TestCo', jobId: 'job-123' });

    expect(res.status).toBe(200);
    expect(res.body.report.overview).toBe('Report overview');
  });
});
