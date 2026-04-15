import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LambdaScrapingService } from '../../../server/services/lambda';

describe('LambdaScrapingService - triggerScrapperStatus & triggerReportStatus', () => {
  let service: LambdaScrapingService;

  beforeEach(() => {
    service = new LambdaScrapingService();

    // Mock sleep to avoid waiting during tests
    vi.spyOn(service as any, 'sleep').mockImplementation(() => Promise.resolve());
  });

  // -----------------------------
  // 1. Scrapper: Immediate success -> completed: true, failed: false
  // -----------------------------
  it('should return completed=true immediately when scrapper status is 2', async () => {
    vi.spyOn(service as any, 'checkJobStatusForScrapper').mockResolvedValue({ scraperStatus: 2, jobId: 'job-1', message: 'Done' });

    const result = await service.triggerScrapperStatus('job-1');
    expect(result).toEqual({ completed: true, failed: false, message: 'Done' });
  });

  // -----------------------------
  // 2. Scrapper: Immediate failure -> completed: false, failed: true
  // -----------------------------
  it('should return failed=true immediately when scrapper status is -1', async () => {
    vi.spyOn(service as any, 'checkJobStatusForScrapper').mockResolvedValue({ scraperStatus: -1, jobId: 'job-2', message: 'Error' });

    const result = await service.triggerScrapperStatus('job-2');
    expect(result).toEqual({ completed: false, failed: true, message: 'Error' });
  });

  // -----------------------------
  // 3. Scrapper: Pending then success -> retries before completion
  // -----------------------------
  it('should retry until scrapper succeeds', async () => {
    const statusMock = vi.fn()
      .mockResolvedValueOnce({ scraperStatus: 0, jobId: 'job-3' })
      .mockResolvedValueOnce({ scraperStatus: 2, jobId: 'job-3', message: 'Done after retry' });

    vi.spyOn(service as any, 'checkJobStatusForScrapper').mockImplementation(statusMock);

    const result = await service.triggerScrapperStatus('job-3');
    expect(statusMock).toHaveBeenCalledTimes(2);
    expect(result).toEqual({ completed: true, failed: false, message: 'Done after retry' });
  });

  // -----------------------------
  // 4. Scrapper: Throws error -> retries until max, then failed
  // -----------------------------
  it('should fail after max retries if checkJobStatusForScrapper throws', async () => {
    vi.spyOn(service as any, 'checkJobStatusForScrapper').mockRejectedValue(new Error('Network error'));

    // reduce maxRetries for fast testing
    (service as any).maxRetriesForScrapper = 3;

    const result = await service.triggerScrapperStatus('job-4');
    expect(result.completed).toBe(false);
    expect(result.failed).toBe(true);
    expect(result.message).toContain('Failed to check job status after 3 attempts');
  });

  // -----------------------------
  // 5. Report: Immediate success -> completed: true, failed: false
  // -----------------------------
  it('should return completed=true immediately when report status is 2', async () => {
    vi.spyOn(service as any, 'checkJobStatusForReport').mockResolvedValue({ reportStatus: 2, reportPath: 'path', message: 'Report done' });

    const result = await service.triggerReportStatus('company', 'job-5');
    expect(result).toEqual({ completed: true, failed: false, message: 'Report done' });
  });

  // -----------------------------
  // 6. Report: Immediate failure -> completed: false, failed: true
  // -----------------------------
  it('should return failed=true immediately when report status is -1', async () => {
    vi.spyOn(service as any, 'checkJobStatusForReport').mockResolvedValue({ reportStatus: -1, reportPath: '', message: 'Report error' });

    const result = await service.triggerReportStatus('company', 'job-6');
    expect(result).toEqual({ completed: false, failed: true, message: 'Report error' });
  });

  // -----------------------------
  // 7. Report: Pending then success -> retries before completion
  // -----------------------------
  it('should retry until report succeeds', async () => {
    const statusMock = vi.fn()
      .mockResolvedValueOnce({ reportStatus: 0, reportPath: 'path' })
      .mockResolvedValueOnce({ reportStatus: 2, reportPath: 'path', message: 'Report done after retry' });

    vi.spyOn(service as any, 'checkJobStatusForReport').mockImplementation(statusMock);

    const result = await service.triggerReportStatus('company', 'job-7');
    expect(statusMock).toHaveBeenCalledTimes(2);
    expect(result).toEqual({ completed: true, failed: false, message: 'Report done after retry' });
  });

  // -----------------------------
  // 8. Report: Throws error -> retries until max, then failed
  // -----------------------------
  it('should fail after max retries if checkJobStatusForReport throws', async () => {
    vi.spyOn(service as any, 'checkJobStatusForReport').mockRejectedValue(new Error('Network error'));

    // reduce maxRetries for fast testing
    (service as any).maxRetriesForReport = 3;

    const result = await service.triggerReportStatus('company', 'job-8');
    expect(result.completed).toBe(false);
    expect(result.failed).toBe(true);
    expect(result.message).toContain('Failed to check report generation status after 3 attempts');
  });
});
