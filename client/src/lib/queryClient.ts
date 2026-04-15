import { QueryClient } from "@tanstack/react-query";
import type { 
  LambdaRequest, 
  AnalysisResponse,
  AnalysisReport,
  JobInitResponse,
  LambdaRequestForStatus
} from "@shared/schema";

// Configuration - use local API
const API_BASE_URL = "";

async function throwIfResNotOk(res: Response) {
  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
}

// Simple API request function
export async function apiRequest(url: string, options: RequestInit = {}) {
  const response = await fetch(url, options);
  await throwIfResNotOk(response);
  return response.json();
}

// Local API functions
export async function startAnalysis(request: LambdaRequestForStatus): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/scrape-data`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  await throwIfResNotOk(response);
  return response.json();
}

export async function getJobId(request: LambdaRequest): Promise<JobInitResponse> {
  const response = await fetch(`${API_BASE_URL}/api/get-jobId`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  await throwIfResNotOk(response);
  return response.json();
}

// Since we're using local API, analysis is synchronous - no polling needed
/*
export async function pollJobUntilComplete(analysis: AnalysisResponse,onProgress?: (progress: number) => void): Promise<AnalysisResponse> {
  // Simulate progress for better UX
  const progressSteps = [10, 25, 45, 60, 75, 90, 99];
  
  for (const progress of progressSteps) {
    if (onProgress) {
      onProgress(progress);
    }
    await new Promise(resolve => setTimeout(resolve, 600));
  }
  
  return analysis;
}
*/

export async function pollJobUntilComplete(analysis: AnalysisResponse,onProgress?: (progress: number) => void): Promise<AnalysisResponse> {
  // Simulate progress for better UX
  const progressSteps = [10, 25, 45, 60, 75, 90, 99];
  
  for (const progress of progressSteps) {
    if (onProgress) {
      onProgress(progress);
    }
    await new Promise(resolve => setTimeout(resolve, 600));
  }
  
  return analysis;
}
// Poll for report from S3
export async function pollForReport(request: LambdaRequestForStatus): Promise<AnalysisReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/poll-report`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  if (response.status === 404) {
    // Report not found after polling timeout
    return null;
  }
  await throwIfResNotOk(response);
  const result = await response.json();
  return result.report;
}

// NEEED TO CHANGES THISESSS!!!!!
export async function getReport(request: LambdaRequestForStatus): Promise<AnalysisReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/get-report`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  if (response.status === 404) {
    // Report not found after polling timeout
    return null;
  }
  await throwIfResNotOk(response);
  const result = await response.json();
  return result.report;
}

// NEED TO CHANGES THISSSSS TOOOO!!!
export async function getImages(request: LambdaRequestForStatus): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/get-images`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  await throwIfResNotOk(response);
  return response.json();
}


export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: false,
      refetchOnWindowFocus: false,
      staleTime: Infinity,
      retry: false,
    },
    mutations: {
      retry: false,
    },
  },
});
