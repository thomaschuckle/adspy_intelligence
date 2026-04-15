import { z } from "zod";

// AWS Lambda API schemas
export const lambdaRequestSchema = z.object({
  companyName: z.string().min(1, "Company name is required"),
  sessionUuid: z.string().min(1, "Session ID is required"),
});

export type LambdaRequest = z.infer<typeof lambdaRequestSchema>;

// AWS Lambda API schemas
export const lambdaRequestSchemaForStatus = z.object({
  companyName : z.string().min(1, "Company name is required"),
  jobId: z.string().min(1, "Job ID is required")
});

export type LambdaRequestForStatus = z.infer<typeof lambdaRequestSchemaForStatus>;

// Lambda response for job initiation
export const lambdaInitResponse = z.object({
  jobId: z.string(),
  status: z.literal("processing"),
  message: z.string(),
});

export type LambdaInitResponse = z.infer<typeof lambdaInitResponse>;

// Lambda response for job status
export const lambdaStatusResponse = z.object({
  jobId: z.string(),
  status: z.enum(["processing", "completed", "failed"]),
  message: z.string(),
  progress: z.number().optional(),
});

export type LambdaStatusResponse = z.infer<typeof lambdaStatusResponse>;

// Job initiation response
export interface JobInitResponse {
  jobId: string;
}

// S3 data structures
export interface AdImage {
  id: string;
  url: string;
  thumbnail: string;
  caption: string;
  //platform: string;
  adNumber?: number;
  companyName?: string;
  campaignId?: string;
  creativeId?: string;
}

export interface AnalysisReport {
  overview: string;
  companyName: string;
  totalAds: number;
}

// Response structure for analysis API endpoints
export interface AnalysisResponse {
  //id: number;
  companyName: string;
  images: AdImage[];
  jobId: string;
  //createdAt: string;
}

