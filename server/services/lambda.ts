// The strucutre that need to be sent to Lambda to get a job id
interface getJobRequest {
  companyName: string;
  sessionUuid: string;
}

// Response from Lambda when getting job ID
interface LambdaResponseJobId {
  jobId: string;
  message?: string;
}

// Lambda response when getting scrapper status & the structure that checkJobStatusForScrapper method returns
interface LambdaScraperResponseStatus {
  jobId: string;
  //status: -1 | 0 | 1 | 2;
  scraperStatus: number;
  scraperRetryCount?:string;
  numAds?:string;
  message?: string;

}
// Lambda response when gettign report status & the structure that checkJobStatusForReport method returns
interface LambdaReportResponseStatus {
  reportStatus: number;
  //status: -1 | 0 | 1 | 2;
  reportPath?: string;
  message?: string;

}

export interface LambdaImage {
  key: string;   // S3 object key
  url: string;   // Presigned URL (valid for 1 hour)
}

// The structure that Lambda returns for s3 images
export interface S3AdImageResponseFromLambda {
  jobId: string;
  companyId: string;
  numImages: number;
  images: LambdaImage[];
}

// The structure that getCompanyImages returns
export interface AdImageReturn {
  id: string;
  url: string;
  thumbnail: string;
  caption: string;
 // platform: string;
  adNumber: number;
  companyName: string;
  campaignId: string;
  creativeId: string;
}

// The structure of Lambda response when getting report
export interface LambdaReportResponseFromLambda {
  //jobId: string;
  //companyId: string;
  reportUrl: string;      // Presigned URL valid for 1 hour
  reportPath: string;     // S3 object key
  companyName:string;
  expiresIn: number;      // URL expiration in seconds
  message: string;
}

// The structure that getCompanyReport method returns
export interface AnalysisReportReturn {
  overview: string;
  companyName:string;
  //totalAds: number;
}

function parseAdFileName(fileName: string): {
  adNumber: number;
  companyName: string;
  campaignId: string;
  creativeId: string;
} | null {
  // Format: ad_{number}_{company}_{campaign_id}_{creative_id}.jpg
  const match = fileName.match(/^ad_(\d+)_([^_]+)_([^_]+)_([^_]+)\.jpg$/);
  
  if (!match) return null;
  
  return {
    adNumber: parseInt(match[1]),
    companyName: match[2],
    campaignId: match[3],
    creativeId: match[4],
  };
}
export class LambdaScrapingService {
  private lambdaApiUrl: string;
  //private lambdaTestApiUrl: string;
  private maxRetriesForScrapper: number = 60; // 60 retries * 5 seconds = 300 seconds max wait
  private retryDelayForScrapper: number = 5000; // 5 seconds between checks
  private maxRetriesForReport: number = 60; // 60 retries * 10 seconds = 600 seconds max wait
  private retryDelayForReport: number = 10000; // 10 seconds between checks

  constructor() {
    this.lambdaApiUrl = process.env.VITE_LAMBDA_API_URL!;
  }

  /**
   * Call the Lambda function to get the job id
   */
  async getJobId(companyName: string,sessionUuid:String): Promise<{ jobId: string; success: boolean; error?: string }> {
    try {
      console.log(`Getting JobId through Lambda for company: ${companyName}`);
      
      const requestBody: getJobRequest = {
        companyName: companyName.trim(),
        sessionUuid: sessionUuid.trim()
      };

      // For now, return a mock response since Lambda is still being developed
      /*
      if (this.lambdaApiUrl.includes('placeholder')) {
        console.log('Using placeholder Lambda response (Lambda still in development)');
        return {
          jobId: `mock-job-${Date.now()}`,
          success: true
        };
      }
      */

      // Real Lambda API call
      const proxyUrl = 'https://corsproxy.io/?';
      const response = await fetch(this.lambdaApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
          //'Authorization': `Bearer ${process.env.LAMBDA_API_KEY || ''}`, // If Lambda requires auth
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`Lambda API returned ${response.status}: ${response.statusText}`);
      }

      const LambdaResponseJobId: LambdaResponseJobId = await response.json();

      console.log(LambdaResponseJobId.jobId);

      return {
        jobId: LambdaResponseJobId.jobId,
        success: true
      };

    } catch (error) {
      console.error('Error triggering Lambda scraping:', error);
      return {
        jobId: '',
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      };
    }
  }

/**
   * Triggers the Lambda function to start generating a report for a company
   */
  async triggerReportStatus(companyName: string, jobId:string): Promise<{ completed: boolean; failed: boolean; message?: string }> {
    console.log(`Waiting for Lambda Report completion: ${jobId}`);

    // For placeholder/mock responses
    /*
    if (jobId.startsWith('mock-job-')) {
      console.log('Mock job detected, simulating completion after 3 seconds');
      await this.sleep(3000);
      return { completed: true, failed: false, message: 'Mock scraping completed successfully' };
    }
    */
    let retries = 0;
    
    while (retries < this.maxRetriesForReport) {
      try {
        const status = await this.checkJobStatusForReport(jobId);
        
        if (status.reportStatus === 2) {
          console.log(`Lambda report generation ${jobId} completed successfully`);
          return { completed: true, failed: false, message: status.message };
        }
        
        if (status.reportStatus === -1) {
          console.log(`Lambda report generatio ${jobId} failed: ${status.message}`);
          return { completed: false, failed: true, message: status.message };
        }
        
        // Job is still pending or processing, wait and retry
        console.log(`Lambda report generation ${jobId} status: ${status.reportStatus}, retrying in ${this.retryDelayForReport}ms..., ${retries} retries`);
        await this.sleep(this.retryDelayForReport);
        retries++;
        
      } catch (error) {
        console.error(`Error checking Lambda report generation status (attempt ${retries + 1}):`, error);
        retries++;
        
        if (retries >= this.maxRetriesForReport) {
          return { 
            completed: false, 
            failed: true, 
            message: `Failed to check report generation status after ${this.maxRetriesForReport} attempts` 
          };
        }
        
        await this.sleep(this.retryDelayForReport);
      }
    }

    return { 
      completed: false, 
      failed: true, 
      message: `Job did not complete within ${this.maxRetriesForReport * this.retryDelayForReport / 1000} seconds` 
    };
  }

  /**
   * Polls Lambda to check the status of a scraping job until completion
   */
  async triggerScrapperStatus(jobId: string): Promise<{ completed: boolean; failed: boolean; message?: string }> {
    console.log(`Waiting for Lambda Scrapper completion: ${jobId}`);

    // For placeholder/mock responses
    /*
    if (jobId.startsWith('mock-job-')) {
      console.log('Mock job detected, simulating completion after 3 seconds');
      await this.sleep(3000);
      return { completed: true, failed: false, message: 'Mock scraping completed successfully' };
    }
    */
    let retries = 0;
    
    while (retries < this.maxRetriesForScrapper) {
      try {
        const status = await this.checkJobStatusForScrapper(jobId);
        
        if (status.scraperStatus === 2) {
          console.log(`Lambda job ${jobId} completed successfully`);
          return { completed: true, failed: false, message: status.message };
          
        }
        
        if (status.scraperStatus === -1) {
          console.log(`Lambda job ${jobId} failed: ${status.message}`);
          return { completed: false, failed: true, message: status.message };
        }
        
        // Job is still pending or processing, wait and retry
        console.log(`Lambda job ${jobId} status: ${status.scraperStatus}, retrying in ${this.retryDelayForScrapper}ms..., ${retries} retries`);
        await this.sleep(this.retryDelayForScrapper);
        retries++;
        
      } catch (error) {
        console.error(`Error checking Lambda job status (attempt ${retries + 1}):`, error);
        retries++;
        
        if (retries >= this.maxRetriesForScrapper) {
          return { 
            completed: false, 
            failed: true, 
            message: `Failed to check job status after ${this.maxRetriesForScrapper} attempts` 
          };
        }
        
        await this.sleep(this.retryDelayForScrapper);
      }
    }

    return { 
      completed: false, 
      failed: true, 
      message: `Job did not complete within ${this.maxRetriesForScrapper * this.retryDelayForScrapper / 1000} seconds` 
    };
  }

  /**
   * Checks the current status of a Lambda scraping job
   */
  private async checkJobStatusForScrapper(jobId: string): Promise<LambdaScraperResponseStatus> {
    // For placeholder API
    /*
    if (this.lambdaApiUrl.includes('placeholder')) {
      throw new Error('Placeholder API - status checking not implemented');
    }
    */

    const proxyUrl = 'https://corsproxy.io/?';
    /*
    const response = await fetch(this.lambdaApiUrl + `/status/${jobId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${process.env.LAMBDA_API_KEY || ''}`,
      }
    });
    */

    const response = await fetch(this.lambdaApiUrl + `/${jobId}/scraper-status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
        //'Authorization': `Bearer ${process.env.LAMBDA_API_KEY || ''}`,
      }
    });

    if (!response.ok) {
      throw new Error(`Status check failed: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  }

    /**
   * Checks the current status of a Lambda scraping job
   */
  private async checkJobStatusForReport(jobId: string): Promise<LambdaReportResponseStatus> {
    // For placeholder API
    /*
    if (this.lambdaApiUrl.includes('placeholder')) {
      throw new Error('Placeholder API - status checking not implemented');
    }
    */

    const proxyUrl = 'https://corsproxy.io/?';
    /*
    const response = await fetch(this.lambdaApiUrl + `/status/${jobId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${process.env.LAMBDA_API_KEY || ''}`,
      }
    });
    */

    const response = await fetch(this.lambdaApiUrl + `/${jobId}/report-status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
        //'Authorization': `Bearer ${process.env.LAMBDA_API_KEY || ''}`,
      }
    });

    if (!response.ok) {
      throw new Error(`Status check failed: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  }
/*
  async getCompanyImages(companyName: string, jobId: string): Promise<S3AdImageResponse> {

    const proxyUrl = 'https://corsproxy.io/?';

    const response = await fetch(proxyUrl +encodeURIComponent(this.lambdaApiUrl + `/${jobId}/images`), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
        //'Authorization': `Bearer ${process.env.LAMBDA_API_KEY || ''}`,
      }
    });

    if (!response.ok) {
      throw new Error(`Status check failed: ${response.status} ${response.statusText}`);
    }

    const LambdaResponseS3Images: S3AdImageResponse = await response.json();
    return LambdaResponseS3Images
  }
*/




  async getCompanyImages(companyName: string, jobId: string): Promise<AdImageReturn[]> {
  const proxyUrl = 'https://corsproxy.io/?';

  const response = await fetch(this.lambdaApiUrl + `/${jobId}/images`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error(`Status check failed: ${response.status} ${response.statusText}`);
  }

  const lambdaResponse: S3AdImageResponseFromLambda = await response.json();
  
  // Transform Lambda response to match original S3AdImage format
  return lambdaResponse.images.map((img, index) => {
    // Parse the key to extract metadata (you'll need to implement parseAdFileName)
    const fileName = img.key.split('/').pop() || '';
    const parsed = parseAdFileName(fileName);
    
    return {
      id: `ad_${parsed?.adNumber || index}`,
      url: img.url,
      thumbnail: img.url,
      caption: `${companyName} - Image ${index + 1}`,
      adNumber: parsed?.adNumber || index,
      companyName: companyName,
      campaignId: parsed?.campaignId || '',
      creativeId: parsed?.creativeId || '',
    };
  });
}

async getCompanyReport(companyName: string, jobId: string): Promise<AnalysisReportReturn | null> {
  try {
    const proxyUrl = 'https://corsproxy.io/?';

    const response = await fetch(this.lambdaApiUrl + `/${jobId}/report`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      // Report not ready or error occurred
      if (response.status === 404) {
        console.log(`Report not found for jobId: ${jobId}`);
        return null;
      }
      throw new Error(`Report fetch failed: ${response.status} ${response.statusText}`);
    }

    const lambdaResponse: LambdaReportResponseFromLambda = await response.json();
    
    // Fetch the actual report content from the presigned URL
    // Don't use proxy for presigned URLs - they already have auth built-in
    console.log(`Fetching report content from presigned URL: ${lambdaResponse.reportUrl}`);
    const reportContentResponse = await fetch(lambdaResponse.reportUrl);
    
    if (!reportContentResponse.ok) {
      const errorText = await reportContentResponse.text();
      console.error(`Failed to fetch report content. Status: ${reportContentResponse.status}, Error: ${errorText}`);
      throw new Error(`Failed to fetch report content from presigned URL: ${reportContentResponse.status} ${reportContentResponse.statusText}`);
    }

    const reportContent = await reportContentResponse.text();
    console.log(`Successfully fetched report content. Length: ${reportContent.length} characters`);
    
    // Clean the content (same as original S3 method)
    const cleanedContent = reportContent
      .replace(/^\s+|\s+$/g, '')
      .replace(/\r\n|\n|\r/g, '');
    
    console.log(`Cleaned content length: ${cleanedContent.length} characters`);
    
    // Parse the JSON
    let jsonData;
    try {
      jsonData = JSON.parse(reportContent);
    } catch (parseError) {
      console.error(`Failed to parse report content as JSON:`, parseError);
      console.error(`Report content preview: ${reportContent.substring(0, 500)}`);
      throw new Error(`Invalid JSON in report content: ${parseError instanceof Error ? parseError.message : 'Unknown error'}`);
    }
    
    // Handle array format with output field
    if (Array.isArray(jsonData) && jsonData.length > 0 && jsonData[0].output) {
      const markdownContent = jsonData[0].output;
      console.log(`Found markdown content in output field`);
      
      // Convert to AnalysisReport format
      const reportData: AnalysisReportReturn = {
        overview: markdownContent,
        companyName: lambdaResponse.companyName
        //totalAds: extractTotalAdsFromMarkdown(markdownContent),
       
        
      };
      
      console.log(`Successfully converted report for ${companyName}`);
      return reportData;
    }
    
    // Fallback: try to parse as direct AnalysisReport
    const reportData = jsonData as AnalysisReportReturn;
    console.log(`Found report for ${companyName}`);
    return reportData;
    
  } catch (error) {
    console.error('Error fetching Lambda report:', error);
    return null;
  }
}

  /**
   * Helper function to sleep for a specified duration
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const lambdaService = new LambdaScrapingService();