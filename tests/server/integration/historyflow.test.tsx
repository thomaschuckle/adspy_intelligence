// tests/integration/historyflow.test.tsx

/**
 * Integration Tests for History Retrieval Flow
 * 
 * These tests validate the historical data retrieval functionality where users
 * can fetch previously scraped data and generated reports using only a jobId.
 * 
 * Test Focus:
 * - Direct retrieval of images without triggering new scrapes
 * - Direct retrieval of reports without triggering new generation
 * - Proper error handling for invalid/missing jobIds
 * - Handling of jobs with no data or incomplete data
 * 
 * What We DON'T Test:
 * - UI text, button labels, or error messages (they change frequently)
 * - Styling or visual elements
 * - Exact message content (only status codes and data structure)
 * 
 * User Flow:
 * 1. User clicks "History" button
 * 2. User enters a jobId
 * 3. System fetches images and report for that jobId
 * 4. User views historical data without triggering new scraping
 */

import { describe, it, beforeEach, afterEach, expect, vi } from "vitest";
import request from "supertest";
import express, { type Express } from "express";
import type { Server } from "http";
import { registerRoutes } from "../../../server/routes";

// Mock the Lambda service to isolate API route testing
// vi.mock is hoisted, so we use vi.fn() factory functions
vi.mock("../../../server/services/lambda", () => {
  return {
    lambdaService: {
      getJobId: vi.fn(),
      triggerScrapperStatus: vi.fn(),
      getCompanyImages: vi.fn(),
      triggerReportStatus: vi.fn(),
      getCompanyReport: vi.fn(),
    },
  };
});

// Import after mocking to ensure mock is applied
import { lambdaService } from "../../../server/services/lambda";

describe("Integration Test: History Retrieval Flow", () => {
  let app: Express;
  let server: Server;

  beforeEach(async () => {
    // Clear all mock call history and results before each test
    vi.clearAllMocks();
    
    // Set up a fresh Express app with routes for each test
    app = express();
    app.use(express.json());
    server = await registerRoutes(app);
  });

  afterEach(() => {
    // Clean up mocks after each test
    vi.clearAllMocks();
  });

  describe("POST /api/get-images - Historical Image Retrieval", () => {
    /**
     * Test #1: Successfully retrieve historical images
     * Expected: Returns 200 with array of images from previous scrape
     * Validates: Users can view old scrape results without triggering new scrapes
     */
    it("should retrieve images for existing jobId", async () => {
      const mockImages = [
        {
          id: "ad_1",
          url: "https://example.com/historical-ad1.jpg",
          thumbnail: "https://example.com/historical-ad1_thumb.jpg",
          caption: "Historical Ad 1",
          adNumber: 1,
          companyName: "HistoryCo",
          campaignId: "campaign_hist_1",
          creativeId: "creative_hist_1",
        },
        {
          id: "ad_2",
          url: "https://example.com/historical-ad2.jpg",
          thumbnail: "https://example.com/historical-ad2_thumb.jpg",
          caption: "Historical Ad 2",
          adNumber: 2,
          companyName: "HistoryCo",
          campaignId: "campaign_hist_2",
          creativeId: "creative_hist_2",
        },
      ];

      // Mock retrieval of historical images from S3
      (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "HistoryCo", jobId: "historical-job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify response structure
      expect(response.body).toHaveProperty("companyName", "HistoryCo");
      expect(response.body).toHaveProperty("jobId", "historical-job-123");
      
      // Verify images array contains data
      expect(response.body.images).toHaveLength(2);
      expect(response.body.images[0]).toHaveProperty("id");
      expect(response.body.images[0]).toHaveProperty("url");
      
      // Verify service was called with correct parameters
      expect(lambdaService.getCompanyImages).toHaveBeenCalledWith("HistoryCo", "historical-job-123");
      
      // Verify scraping was NOT triggered (no call to triggerScrapperStatus)
      expect(lambdaService.triggerScrapperStatus).not.toHaveBeenCalled();
    });

    /**
     * Test #2: Handle job with no images
     * Expected: Returns 200 with empty array
     * Validates: Graceful handling when historical job has no images
     */
    it("should handle jobId with no images", async () => {
      // Mock empty images array (job exists but has no ads)
      (lambdaService.getCompanyImages as any).mockResolvedValue([]);

      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "EmptyHistoryCo", jobId: "empty-job-456" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify empty array is returned
      expect(response.body.images).toHaveLength(0);
      
      // Verify scraping was NOT triggered
      expect(lambdaService.triggerScrapperStatus).not.toHaveBeenCalled();
    });

    /**
     * Test #3: Handle invalid/non-existent jobId
     * Expected: Returns 500 with error
     * Validates: Error handling for jobs that don't exist in system
     */
    it("should handle non-existent jobId for images", async () => {
      // Mock service throwing error for non-existent job
      (lambdaService.getCompanyImages as any).mockRejectedValue(
        new Error("Job not found")
      );

      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "NonExistentCo", jobId: "non-existent-789" });

      // Verify error status code
      expect(response.status).toBe(500);
      
      // Verify error response structure
      expect(response.body).toHaveProperty("success", false);
    });

    /**
     * Test #4: Handle missing required fields
     * Expected: Returns 400 for validation error
     * Validates: Request validation for history retrieval
     */
    it("should return 400 for missing jobId", async () => {
      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "TestCo" }); // Missing jobId

      // Verify bad request status code
      expect(response.status).toBe(400);
    });
  });

  describe("POST /api/get-report - Historical Report Retrieval", () => {
    /**
     * Test #5: Successfully retrieve historical report
     * Expected: Returns 200 with report data from previous generation
     * Validates: Users can view old reports without triggering new generation
     */
    it("should retrieve report for existing jobId", async () => {
      const mockReport = {
        overview: "# Historical Report\n\nThis is a previously generated report with analysis data.",
        companyName: "HistoryCo",
      };

      // Mock retrieval of historical report from S3
      (lambdaService.getCompanyReport as any).mockResolvedValue(mockReport);

      const response = await request(app)
        .post("/api/get-report")
        .send({ companyName: "HistoryCo", jobId: "historical-job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify response structure
      expect(response.body).toHaveProperty("success", true);
      expect(response.body).toHaveProperty("companyName", "HistoryCo");
      
      // Verify report data structure
      expect(response.body.report).toHaveProperty("overview");
      expect(response.body.report).toHaveProperty("companyName", "HistoryCo");
      expect(response.body.report.overview).toContain("Historical Report");
      
      // Verify service was called with correct parameters
      expect(lambdaService.getCompanyReport).toHaveBeenCalledWith("HistoryCo", "historical-job-123");
      
      // Verify report generation was NOT triggered
      expect(lambdaService.triggerReportStatus).not.toHaveBeenCalled();
    });

    /**
     * Test #6: Handle job with no report
     * Expected: Returns 404 status code
     * Validates: Proper 404 when job exists but report was never generated
     */
    it("should handle jobId with no report", async () => {
      // Mock report not found (returns null)
      (lambdaService.getCompanyReport as any).mockResolvedValue(null);

      const response = await request(app)
        .post("/api/get-report")
        .send({ companyName: "NoReportCo", jobId: "no-report-456" });

      // Verify not found status code
      expect(response.status).toBe(404);
      
      // Verify error response structure
      expect(response.body).toHaveProperty("success", false);
      
      // Verify report generation was NOT triggered
      expect(lambdaService.triggerReportStatus).not.toHaveBeenCalled();
    });

    /**
     * Test #7: Handle invalid/non-existent jobId
     * Expected: Returns 404 or 500 with error
     * Validates: Error handling for jobs that don't exist
     */
    it("should handle non-existent jobId for report", async () => {
      // Mock service throwing error for non-existent job
      (lambdaService.getCompanyReport as any).mockRejectedValue(
        new Error("Job not found")
      );

      const response = await request(app)
        .post("/api/get-report")
        .send({ companyName: "NonExistentCo", jobId: "non-existent-789" });

      // Verify error status code (500 for server errors)
      expect(response.status).toBe(500);
      
      // Verify error response structure
      expect(response.body).toHaveProperty("success", false);
    });

    /**
     * Test #8: Handle missing required fields
     * Expected: Returns 400 for validation error
     * Validates: Request validation for history retrieval
     */
    it("should return 400 for missing jobId", async () => {
      const response = await request(app)
        .post("/api/get-report")
        .send({ companyName: "TestCo" }); // Missing jobId

      // Verify bad request status code
      expect(response.status).toBe(400);
    });
  });

  describe("Complete History Flow: Retrieve Both Images and Report", () => {
    /**
     * Test #9: Successfully retrieve complete historical data
     * Expected: Both images and report endpoints return 200 with data
     * Validates: Users can view complete historical analysis
     * 
     * Flow:
     * 1. User enters jobId
     * 2. System fetches historical images
     * 3. System fetches historical report
     * 4. No new scraping or generation is triggered
     */
    it("should retrieve both images and report for jobId", async () => {
      const mockJobId = "complete-history-123";
      const mockImages = [
        {
          id: "ad_1",
          url: "https://example.com/complete-ad1.jpg",
          thumbnail: "https://example.com/complete-ad1_thumb.jpg",
          caption: "Complete Historical Ad",
          adNumber: 1,
          companyName: "CompleteCo",
          campaignId: "campaign_1",
          creativeId: "creative_1",
        },
      ];
      const mockReport = {
        overview: "# Complete Historical Analysis\n\nFull report data.",
        companyName: "CompleteCo",
      };

      // Step 1: Fetch historical images
      (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

      const imagesResponse = await request(app)
        .post("/api/get-images")
        .send({ companyName: "CompleteCo", jobId: mockJobId });

      expect(imagesResponse.status).toBe(200);
      expect(imagesResponse.body.images).toHaveLength(1);

      // Step 2: Fetch historical report
      (lambdaService.getCompanyReport as any).mockResolvedValue(mockReport);

      const reportResponse = await request(app)
        .post("/api/get-report")
        .send({ companyName: "CompleteCo", jobId: mockJobId });

      expect(reportResponse.status).toBe(200);
      expect(reportResponse.body.report.overview).toContain("Complete Historical Analysis");

      // Verify NO scraping or generation was triggered
      expect(lambdaService.triggerScrapperStatus).not.toHaveBeenCalled();
      expect(lambdaService.triggerReportStatus).not.toHaveBeenCalled();
      expect(lambdaService.getJobId).not.toHaveBeenCalled();
    });

    /**
     * Test #10: Handle partial historical data (images exist, no report)
     * Expected: Images return 200, report returns 404
     * Validates: Graceful handling when job is incomplete
     */
    it("should handle jobId with images but no report", async () => {
      const mockJobId = "partial-history-456";
      const mockImages = [
        {
          id: "ad_1",
          url: "https://example.com/partial-ad1.jpg",
          thumbnail: "https://example.com/partial-ad1_thumb.jpg",
          caption: "Partial Historical Ad",
          adNumber: 1,
          companyName: "PartialCo",
          campaignId: "campaign_1",
          creativeId: "creative_1",
        },
      ];

      // Images exist
      (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

      const imagesResponse = await request(app)
        .post("/api/get-images")
        .send({ companyName: "PartialCo", jobId: mockJobId });

      expect(imagesResponse.status).toBe(200);
      expect(imagesResponse.body.images).toHaveLength(1);

      // Report doesn't exist
      (lambdaService.getCompanyReport as any).mockResolvedValue(null);

      const reportResponse = await request(app)
        .post("/api/get-report")
        .send({ companyName: "PartialCo", jobId: mockJobId });

      expect(reportResponse.status).toBe(404);
      
      // Verify NO generation was triggered
      expect(lambdaService.triggerReportStatus).not.toHaveBeenCalled();
    });

    /**
     * Test #11: Handle completely missing historical data
     * Expected: Both endpoints return errors (404/500)
     * Validates: Proper error handling when jobId has no associated data
     */
    it("should handle jobId with no data at all", async () => {
      const mockJobId = "missing-data-789";

      // No images found
      (lambdaService.getCompanyImages as any).mockResolvedValue([]);

      const imagesResponse = await request(app)
        .post("/api/get-images")
        .send({ companyName: "MissingCo", jobId: mockJobId });

      expect(imagesResponse.status).toBe(200);
      expect(imagesResponse.body.images).toHaveLength(0);

      // No report found
      (lambdaService.getCompanyReport as any).mockResolvedValue(null);

      const reportResponse = await request(app)
        .post("/api/get-report")
        .send({ companyName: "MissingCo", jobId: mockJobId });

      expect(reportResponse.status).toBe(404);
      
      // Verify NO new jobs were created
      expect(lambdaService.getJobId).not.toHaveBeenCalled();
      expect(lambdaService.triggerScrapperStatus).not.toHaveBeenCalled();
      expect(lambdaService.triggerReportStatus).not.toHaveBeenCalled();
    });
  });
});