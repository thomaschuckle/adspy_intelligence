import type { Express } from "express";
import { createServer, type Server } from "http";
//import { storage } from "./storage";
import { lambdaRequestSchema, lambdaRequestSchemaForStatus, type AnalysisResponse, type JobInitResponse } from "@shared/schema";
//import { generateCompetitiveAnalysis } from "./services/openai";
import { lambdaService } from "./services/lambda";
import { ZodError } from "zod";
//import { getCompanyImages, testS3Connection, pollForReport, getCompanyReport,} from "./services/s3";
export async function registerRoutes(app: Express): Promise<Server> {
  
  

  // Scrape images using Lambda function
  app.post("/api/get-jobId", async (req, res) => {
    try {
      const { companyName, sessionUuid } = lambdaRequestSchema.parse(req.body);
      
      
      console.log(`Calling Lambda API to get jobID for : ${companyName}`);
      
      // Step 1: Trigger Lambda function to start scraping
      const triggerJobApi = await lambdaService.getJobId(companyName, sessionUuid);
      
      if (!triggerJobApi.success) {
        return res.status(500).json({
          success: false,
          message: `Failed to get JobId through Lambda : ${triggerJobApi.error}`
        });
      }
      
      console.log(`Lambda jobId successfully retrieve with ID: ${triggerJobApi.jobId}`);
      

      const response: JobInitResponse = {
        //id: analysis.id,
        jobId:triggerJobApi.jobId
        
        //createdAt: analysis.createdAt.toISOString(),
      };

      res.json(response);
      /*
      res.json({
        success: true,
        companyName,
        images: s3Images,
        jobId: triggerResult.jobId,
        message: `Successfully scraped and retrieved ${s3Images.length} images for ${companyName}`,
        scrapedAt: new Date().toISOString()
      });
      */
      
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({ error: error.errors });
      }

      console.error("Lambda scraping error:", error);
      return res.status(500).json({
        success: false,
        message: "Failed to scrape images: " + (error as Error).message
      });
    }
  });

  // Scrape images using Lambda function
  app.post("/api/scrape-data", async (req, res) => {
    
    try {
      const { companyName,jobId } = lambdaRequestSchemaForStatus.parse(req.body);
     
      
      console.log(`Trigger Lambda scraping & getting status for: ${companyName}`);
      
      // Step 1: Trigger Lambda function to start scraping and get the status of desire jobId
      //const triggerResult = await lambdaService.waitForCompletion(jobId);
      
      /*
      if (!triggerResult.success) {
        return res.status(500).json({
          success: false,
          message: `Failed to trigger Lambda scraping: ${triggerResult.error}`
        });
      }
      
      console.log(`Lambda job triggered successfully with ID: ${triggerResult.jobId}`);
      */

      // Step 1: Trigger Lambda function to start scraping and get the status of desire jobId
      const completionResult = await lambdaService.triggerScrapperStatus(jobId);
      //const completionResult = await lambdaService.waitForCompletion('mock-job-');
      if (completionResult.failed) {
        return res.status(500).json({
          success: false,
          message: `Lambda scraping failed: ${completionResult.message}`
        });
      }
      
      if (!completionResult.completed) {
        return res.status(408).json({
          success: false,
          message: `Lambda scraping timed out: ${completionResult.message}`
        });
      }
      
      console.log(`Lambda job completed successfully: ${completionResult.message}`);
      
      // Step 3: Fetch scraped images from S3 using existing function
      //const s3Images = await getCompanyImages(companyName);
      const s3Images = await lambdaService.getCompanyImages(companyName,jobId);
      /*
      if (s3Images.length === 0) {
        return res.status(404).json({
          success: false,
          message: `No images found for ${companyName} after Lambda scraping. The scraping may have failed or no ads were found.`
        });
      }
        */
      
      console.log(`Successfully retrieved ${s3Images.length} images from S3`);
      
      // Step 4: Return scraped images to frontend

      const response: AnalysisResponse = {
        //id: analysis.id,
        companyName: companyName,
        images: s3Images,
        jobId: jobId,
        //createdAt: analysis.createdAt.toISOString(),
      };

      res.json(response);
      /*
      res.json({
        success: true,
        companyName,
        images: s3Images,
        jobId: triggerResult.jobId,
        message: `Successfully scraped and retrieved ${s3Images.length} images for ${companyName}`,
        scrapedAt: new Date().toISOString()
      });
      */
      
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({ error: error.errors });
      }

      console.error("Lambda scraping error:", error);
      return res.status(500).json({
        success: false,
        message: "Failed to scrape images: " + (error as Error).message
      });
    }
  });

  // Poll for report from S3
  app.post("/api/poll-report", async (req, res) => {
    try {
      const { companyName, jobId } = lambdaRequestSchemaForStatus.parse(req.body);
      
      /*
      console.log(`Starting Report polling for: ${companyName}`);
      
      // Poll S3 for report with 1-minute timeout
      const report = await pollForReport(companyName, 30, 2000); // 30 attempts * 2 seconds = 60 seconds
      */
     console.log(`Starting Lambda-based report generation for: ${companyName}`);
      
      // Step 1: Trigger Lambda for report generation
      const completionResult = await lambdaService.triggerReportStatus(companyName,jobId);
      
      if (completionResult.failed) {
        return res.status(500).json({
          success: false,
          message: `Lambda report generation failed: ${completionResult.message}`
        });
      }
      
      if (!completionResult.completed) {
        return res.status(408).json({
          success: false,
          message: `Lambda report generation timed out: ${completionResult.message}`
        });
      }
      
      console.log(`Lambda report job completed successfully: ${completionResult.message}`);
      
      // Step 3: Fetch the generated report from S3
      const report = await lambdaService.getCompanyReport(companyName,jobId);

      if (!report) {
        return res.status(404).json({
          success: false,
          message: `Report not found for ${companyName} after 60 seconds of polling. The report may still be generating.`
        });
      }
      
      console.log(`Successfully retrieved report for ${companyName}`);
      
      res.json({
        success: true,
        companyName,
        report,
        message: `Report successfully retrieved for ${companyName}`,
        retrievedAt: new Date().toISOString()
      });
      
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({ error: error.errors });
      }

      console.error("Report polling error:", error);
      return res.status(500).json({
        success: false,
        message: "Failed to poll for report: " + (error as Error).message
      });
    }
  });
  
  // Get images directly using Lambda function
  app.post("/api/get-images", async (req, res) => {
    
    try {
      const { companyName,jobId } = lambdaRequestSchemaForStatus.parse(req.body);
      
      // Step 3: Fetch scraped images from S3 using existing function
      //const s3Images = await getCompanyImages(companyName);
      const s3Images = await lambdaService.getCompanyImages(companyName,jobId);
      
      console.log(`Successfully retrieved ${s3Images.length} images from S3`);
      
      // Step 4: Return scraped images to frontend

      const response: AnalysisResponse = {
        //id: analysis.id,
        companyName: companyName,
        images: s3Images,
        jobId: jobId,
        //createdAt: analysis.createdAt.toISOString(),
      };

      res.json(response);

      
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({ error: error.errors });
      }

      console.error("Lambda scraping error:", error);
      return res.status(500).json({
        success: false,
        message: "Failed to scrape images: " + (error as Error).message
      });
    }
  });

  //NEEDDD TO CHANGES THISSSSSS!!!!
  // Get directly for report from S3
  app.post("/api/get-report", async (req, res) => {
    try {
      const { companyName, jobId } = lambdaRequestSchemaForStatus.parse(req.body);
      
      // Step 3: Fetch the generated report from S3
      const report = await lambdaService.getCompanyReport(companyName,jobId);

      if (!report) {
        return res.status(404).json({
          success: false,
          message: `Report not found for ${companyName} after 60 seconds of polling. The report may still be generating.`
        });
      }
      
      console.log(`Successfully retrieved report for ${companyName}`);
      
      res.json({
        success: true,
        companyName,
        report,
        message: `Report successfully retrieved for ${companyName}`,
        retrievedAt: new Date().toISOString()
      });
      
    } catch (error) {
      if (error instanceof ZodError) {
        return res.status(400).json({ error: error.errors });
      }

      console.error("Report polling error:", error);
      return res.status(500).json({
        success: false,
        message: "Failed to poll for report: " + (error as Error).message
      });
    }
  });

  // Test S3 connection
  /*
  app.get("/api/test-s3", async (req, res) => {
    try {
      const connected = await testS3Connection();
      res.json({ 
        connected, 
        bucket: "test-1-adspy",
        region: "ap-south-1",
        message: connected ? "S3 connection successful" : "S3 connection failed"
      });
    } catch (error) {
      res.status(500).json({ 
        connected: false, 
        message: "S3 test failed: " + (error as Error).message 
      });
    }
  });*/

  const httpServer = createServer(app);
  return httpServer;
}

