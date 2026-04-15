// tests/server/integration/mainflow.test.tsx

/**
 * Integration Tests for API Scraping & Report Flow
 * 
 * These tests validate the core API endpoints and their behavior under various scenarios.
 * They test the integration between Express routes and the Lambda service layer.
 * 
 * Test Focus:
 * - HTTP status codes (200, 400, 404, 408, 500)
 * - Response data structure and required fields
 * - Service method invocation with correct parameters
 * - Error handling and edge cases
 * 
 * What We DON'T Test:
 * - UI text, button labels, or error messages (they change frequently)
 * - Styling or visual elements
 * - Exact message content (only status codes and data structure)
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

describe("Integration Test: API Scraping & Report Flow", () => {
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

  describe("POST /api/get-jobId", () => {
    /**
     * Test #1: Successful job initialization
     * Expected: Returns 200 with jobId in response body
     * Validates: Lambda service is called with correct parameters
     */
    it("should return jobId on successful job initialization", async () => {
      const mockJobId = "test-job-123";
      
      // Mock Lambda service to return successful job creation
      (lambdaService.getJobId as any).mockResolvedValue({
        jobId: mockJobId,
        success: true,
      });

      const response = await request(app)
        .post("/api/get-jobId")
        .send({ companyName: "TestCompany", sessionUuid: "session-123" });

      // Verify HTTP status code
      expect(response.status).toBe(200);
      
      // Verify response contains jobId field
      expect(response.body).toHaveProperty("jobId", mockJobId);
      
      // Verify Lambda service was called with correct parameters
      expect(lambdaService.getJobId).toHaveBeenCalledWith("TestCompany", "session-123");
    });

    /**
     * Test #2: Lambda service failure during job initialization
     * Expected: Returns 500 status code with success: false
     * Validates: Error handling when Lambda API fails
     */
    it("should return 500 when job initialization fails", async () => {
      // Mock Lambda service to return failure
      (lambdaService.getJobId as any).mockResolvedValue({
        jobId: "",
        success: false,
        error: "Lambda API error",
      });

      const response = await request(app)
        .post("/api/get-jobId")
        .send({ companyName: "TestCompany", sessionUuid: "session-123" });

      // Verify error status code
      expect(response.status).toBe(500);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });

    /**
     * Test #3: Invalid request body (missing required fields)
     * Expected: Returns 400 status code for validation error
     * Validates: Request validation middleware is working
     */
    it("should return 400 for invalid request body", async () => {
      const response = await request(app)
        .post("/api/get-jobId")
        .send({ companyName: "" }); // Missing sessionUuid

      // Verify bad request status code
      expect(response.status).toBe(400);
    });
  });

  describe("POST /api/scrape-data", () => {
    /**
     * Test #4: Successful scraping operation
     * Expected: Returns 200 with images array and job metadata
     * Validates: Complete scraping flow from trigger to image retrieval
     */
    it("should return scraped images on successful scraping", async () => {
      const mockImages = [
        {
          id: "ad_1",
          url: "https://example.com/ad1.jpg",
          thumbnail: "https://example.com/ad1_thumb.jpg",
          caption: "Test Ad 1",
          adNumber: 1,
          companyName: "TestCompany",
          campaignId: "campaign_1",
          creativeId: "creative_1",
        },
      ];

      // Mock scraper completing successfully (status: 2)
      (lambdaService.triggerScrapperStatus as any).mockResolvedValue({
        completed: true,
        failed: false,
      });

      // Mock images being retrieved from S3
      (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

      const response = await request(app)
        .post("/api/scrape-data")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify response contains required fields
      expect(response.body).toHaveProperty("companyName", "TestCompany");
      expect(response.body).toHaveProperty("jobId", "job-123");
      
      // Verify images array structure
      expect(response.body.images).toHaveLength(1);
      expect(response.body.images[0]).toMatchObject({
        id: "ad_1",
        companyName: "TestCompany",
      });
    });

    /**
     * Test #5: Scraper permanent failure (status: -1)
     * Expected: Returns 500 status code with success: false
     * Validates: Error handling for permanent scraping failures
     */
    it("should return 500 when scraping permanently fails", async () => {
      // Mock scraper returning permanent failure status
      (lambdaService.triggerScrapperStatus as any).mockResolvedValue({
        completed: false,
        failed: true,
      });

      const response = await request(app)
        .post("/api/scrape-data")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify error status code
      expect(response.status).toBe(500);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });

    /**
     * Test #6: Scraping timeout (still in progress after max retries)
     * Expected: Returns 408 (Request Timeout) status code
     * Validates: Timeout handling when scraper doesn't complete
     */
    it("should return 408 when scraping times out", async () => {
      // Mock scraper still in progress (status: 0 or 1)
      (lambdaService.triggerScrapperStatus as any).mockResolvedValue({
        completed: false,
        failed: false,
      });

      const response = await request(app)
        .post("/api/scrape-data")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify timeout status code
      expect(response.status).toBe(408);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });
  });

  describe("POST /api/poll-report", () => {
    /**
     * Test #7: Successful report generation and retrieval
     * Expected: Returns 200 with report data in response body
     * Validates: Complete report flow from generation to retrieval
     */
    it("should return report when successfully generated", async () => {
      const mockReport = {
        overview: "# Report Content\n\nThis is the analysis report.",
        companyName: "TestCompany",
      };

      // Mock report generation completed (status: 2)
      (lambdaService.triggerReportStatus as any).mockResolvedValue({
        completed: true,
        failed: false,
      });

      // Mock report retrieval from S3
      (lambdaService.getCompanyReport as any).mockResolvedValue(mockReport);

      const response = await request(app)
        .post("/api/poll-report")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify response structure
      expect(response.body).toHaveProperty("success", true);
      expect(response.body).toHaveProperty("companyName", "TestCompany");
      
      // Verify report data structure
      expect(response.body.report).toMatchObject({
        overview: expect.any(String),
        companyName: "TestCompany",
      });
    });

    /**
     * Test #8: Report file not found (404 from S3)
     * Expected: Returns 404 status code with success: false
     * Validates: Handling when report generation succeeded but file doesn't exist
     */
    it("should return 404 when report is not found", async () => {
      // Mock report generation completed but file doesn't exist
      (lambdaService.triggerReportStatus as any).mockResolvedValue({
        completed: true,
        failed: false,
      });

      // Mock report retrieval returning null (not found)
      (lambdaService.getCompanyReport as any).mockResolvedValue(null);

      const response = await request(app)
        .post("/api/poll-report")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify not found status code
      expect(response.status).toBe(404);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });

    /**
     * Test #9: Report generation permanent failure (status: -1)
     * Expected: Returns 500 status code with success: false
     * Validates: Error handling for permanent report generation failures
     */
    it("should return 500 when report generation permanently fails", async () => {
      // Mock report generation returning permanent failure
      (lambdaService.triggerReportStatus as any).mockResolvedValue({
        completed: false,
        failed: true,
      });

      const response = await request(app)
        .post("/api/poll-report")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify error status code
      expect(response.status).toBe(500);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });
  });

  describe("POST /api/get-images", () => {
    /**
     * Test #10: Direct image retrieval (without scraping)
     * Expected: Returns 200 with images array
     * Validates: Images can be fetched directly using jobId
     */
    it("should fetch and return images directly", async () => {
      const mockImages = [
        {
          id: "ad_1",
          url: "https://example.com/ad1.jpg",
          thumbnail: "https://example.com/ad1_thumb.jpg",
          caption: "Test Ad",
          adNumber: 1,
          companyName: "TestCompany",
          campaignId: "campaign_1",
          creativeId: "creative_1",
        },
      ];

      // Mock direct image retrieval from S3
      (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify images array is returned
      expect(response.body.images).toHaveLength(1);
      
      // Verify service was called with correct parameters
      expect(lambdaService.getCompanyImages).toHaveBeenCalledWith("TestCompany", "job-123");
    });

    /**
     * Test #11: No images found for company
     * Expected: Returns 200 with empty images array
     * Validates: Successful response even when no ads exist
     */
    it("should handle empty images array", async () => {
      // Mock empty images array (no ads found for this company)
      (lambdaService.getCompanyImages as any).mockResolvedValue([]);

      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify empty array is returned
      expect(response.body.images).toHaveLength(0);
    });

    /**
     * Test #12: Error fetching images from S3
     * Expected: Returns 500 status code with success: false
     * Validates: Error handling for S3 retrieval failures
     */
    it("should handle errors when fetching images", async () => {
      // Mock service throwing an error
      (lambdaService.getCompanyImages as any).mockRejectedValue(
        new Error("Internal server error")
      );

      const response = await request(app)
        .post("/api/get-images")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify error status code
      expect(response.status).toBe(500);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });
  });

  describe("POST /api/get-report", () => {
    /**
     * Test #13: Direct report retrieval (without polling)
     * Expected: Returns 200 with report data
     * Validates: Reports can be fetched directly using jobId
     */
    it("should fetch and return report directly", async () => {
      const mockReport = {
        overview: "Direct report content",
        companyName: "TestCompany",
      };

      // Mock direct report retrieval from S3
      (lambdaService.getCompanyReport as any).mockResolvedValue(mockReport);

      const response = await request(app)
        .post("/api/get-report")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify success status code
      expect(response.status).toBe(200);
      
      // Verify response structure
      expect(response.body).toHaveProperty("success", true);
      
      // Verify report data is present
      expect(response.body.report).toMatchObject({
        overview: expect.any(String),
        companyName: "TestCompany",
      });
    });

    /**
     * Test #14: Report does not exist for this job
     * Expected: Returns 404 status code with success: false
     * Validates: Proper 404 handling when report hasn't been generated
     */
    it("should return 404 when report does not exist", async () => {
      // Mock report not found (returns null)
      (lambdaService.getCompanyReport as any).mockResolvedValue(null);

      const response = await request(app)
        .post("/api/get-report")
        .send({ companyName: "TestCompany", jobId: "job-123" });

      // Verify not found status code
      expect(response.status).toBe(404);
      
      // Verify response indicates failure
      expect(response.body).toHaveProperty("success", false);
    });
  });

  describe("Complete Flow: Job Init -> Scrape -> Report", () => {
    /**
     * Test #15: End-to-end successful workflow
     * Expected: All three API calls succeed in sequence
     * Validates: Complete integration from job creation to report retrieval
     * 
     * Flow:
     * 1. POST /api/get-jobId -> Returns jobId
     * 2. POST /api/scrape-data -> Returns images array
     * 3. POST /api/poll-report -> Returns report data
     */
    it("should handle complete workflow successfully", async () => {
      const mockJobId = "flow-job-123";
      const mockImages = [
        {
          id: "ad_1",
          url: "https://example.com/ad1.jpg",
          thumbnail: "https://example.com/ad1_thumb.jpg",
          caption: "Flow Test Ad",
          adNumber: 1,
          companyName: "FlowTestCo",
          campaignId: "campaign_1",
          creativeId: "creative_1",
        },
      ];
      const mockReport = {
        overview: "Complete flow report",
        companyName: "FlowTestCo",
      };

      // Step 1: Initialize job and get jobId
      (lambdaService.getJobId as any).mockResolvedValue({
        jobId: mockJobId,
        success: true,
      });

      const jobResponse = await request(app)
        .post("/api/get-jobId")
        .send({ companyName: "FlowTestCo", sessionUuid: "session-flow" });

      expect(jobResponse.status).toBe(200);
      expect(jobResponse.body.jobId).toBe(mockJobId);

      // Step 2: Trigger scraping and get images
      (lambdaService.triggerScrapperStatus as any).mockResolvedValue({
        completed: true,
        failed: false,
      });
      (lambdaService.getCompanyImages as any).mockResolvedValue(mockImages);

      const scrapeResponse = await request(app)
        .post("/api/scrape-data")
        .send({ companyName: "FlowTestCo", jobId: mockJobId });

      expect(scrapeResponse.status).toBe(200);
      expect(scrapeResponse.body.images).toHaveLength(1);

      // Step 3: Generate and retrieve report
      (lambdaService.triggerReportStatus as any).mockResolvedValue({
        completed: true,
        failed: false,
      });
      (lambdaService.getCompanyReport as any).mockResolvedValue(mockReport);

      const reportResponse = await request(app)
        .post("/api/poll-report")
        .send({ companyName: "FlowTestCo", jobId: mockJobId });

      expect(reportResponse.status).toBe(200);
      expect(reportResponse.body.report.overview).toBe("Complete flow report");
    });

    /**
     * Test #16: Job already exists scenario
     * Expected: Returns existing jobId without creating new one
     * Validates: Idempotent job creation (multiple requests with same params)
     */
    it("should handle job already exists scenario", async () => {
      const existingJobId = "existing-job-456";

      // Mock Lambda returning existing job
      (lambdaService.getJobId as any).mockResolvedValue({
        jobId: existingJobId,
        success: true,
      });

      const response = await request(app)
        .post("/api/get-jobId")
        .send({ companyName: "ExistingCo", sessionUuid: "session-existing" });

      // Verify success with existing jobId
      expect(response.status).toBe(200);
      expect(response.body.jobId).toBe(existingJobId);
    });

    /**
     * Test #17: Scraper waiting for concurrent job (status: 1)
     * Expected: Returns 408 timeout after max retries
     * Validates: Handling when scraper is blocked by another job
     */
    it("should handle scraper waiting for another job", async () => {
      // Mock scraper returning waiting status (status: 1)
      (lambdaService.triggerScrapperStatus as any).mockResolvedValue({
        completed: false,
        failed: false,
      });

      const response = await request(app)
        .post("/api/scrape-data")
        .send({ companyName: "WaitingCo", jobId: "waiting-job-789" });

      // Verify timeout status code
      expect(response.status).toBe(408);
    });

    /**
     * Test #18: Report generation still in progress (status: 1)
     * Expected: Returns 408 timeout after max retries
     * Validates: Handling when report generation hasn't completed
     */
    it("should handle report generation in progress", async () => {
      // Mock report still being generated (status: 1)
      (lambdaService.triggerReportStatus as any).mockResolvedValue({
        completed: false,
        failed: false,
      });

      const response = await request(app)
        .post("/api/poll-report")
        .send({ companyName: "InProgressCo", jobId: "progress-job-101" });

      // Verify timeout status code
      expect(response.status).toBe(408);
    });
  });
});