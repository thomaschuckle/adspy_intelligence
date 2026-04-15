// tests/shared/schema.test.ts
import { describe, it, expect } from "vitest";
import { 
  lambdaRequestSchema, 
  lambdaRequestSchemaForStatus, 
  lambdaInitResponse, 
  lambdaStatusResponse 
} from "@shared/schema";

describe("Zod Schema Validation Tests", () => {

  // -----------------------------
  // 1. lambdaRequestSchema
  // -----------------------------
  describe("lambdaRequestSchema", () => {
    it("should pass with valid input", () => {
      const data = { companyName: "Apple", sessionUuid: "abc123" };
      expect(() => lambdaRequestSchema.parse(data)).not.toThrow();
    });

    it("should throw when fields are empty", () => {
      const data = { companyName: "", sessionUuid: "" };
      expect(() => lambdaRequestSchema.parse(data)).toThrow();
    });

    it("should throw when fields are missing", () => {
      const data = { companyName: "Apple" };
      expect(() => lambdaRequestSchema.parse(data as any)).toThrow();
    });
  });

  // -----------------------------
  // 2. lambdaRequestSchemaForStatus
  // -----------------------------
  describe("lambdaRequestSchemaForStatus", () => {
    it("should pass with valid input", () => {
      const data = { companyName: "Apple", jobId: "job-123" };
      expect(() => lambdaRequestSchemaForStatus.parse(data)).not.toThrow();
    });

    it("should throw when fields are empty", () => {
      const data = { companyName: "", jobId: "" };
      expect(() => lambdaRequestSchemaForStatus.parse(data)).toThrow();
    });

    it("should throw when fields are missing", () => {
      const data = { jobId: "job-123" };
      expect(() => lambdaRequestSchemaForStatus.parse(data as any)).toThrow();
    });
  });

  // -----------------------------
  // 3. lambdaInitResponse
  // -----------------------------
  describe("lambdaInitResponse", () => {
    it("should pass with valid input", () => {
      const data = { jobId: "job-123", status: "processing", message: "Job started" };
      expect(() => lambdaInitResponse.parse(data)).not.toThrow();
    });

    it("should throw when status is invalid", () => {
      const data = { jobId: "job-123", status: "done", message: "Job started" };
      expect(() => lambdaInitResponse.parse(data as any)).toThrow();
    });

    it("should throw when required fields are missing", () => {
      const data = { jobId: "job-123", status: "processing" };
      expect(() => lambdaInitResponse.parse(data as any)).toThrow();
    });
  });

  // -----------------------------
  // 4. lambdaStatusResponse
  // -----------------------------
  describe("lambdaStatusResponse", () => {
    it("should pass with valid input", () => {
      const data = { jobId: "job-123", status: "completed", message: "Done" };
      expect(() => lambdaStatusResponse.parse(data)).not.toThrow();
    });

    it("should pass with optional progress", () => {
      const data = { jobId: "job-123", status: "processing", message: "Working", progress: 50 };
      expect(() => lambdaStatusResponse.parse(data)).not.toThrow();
    });

    it("should throw when status is invalid", () => {
      const data = { jobId: "job-123", status: "unknown", message: "Working" };
      expect(() => lambdaStatusResponse.parse(data as any)).toThrow();
    });

    it("should throw when required fields are missing", () => {
      const data = { status: "completed", message: "Done" };
      expect(() => lambdaStatusResponse.parse(data as any)).toThrow();
    });
  });

});
