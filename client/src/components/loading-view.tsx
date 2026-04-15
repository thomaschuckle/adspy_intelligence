import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { startAnalysis, getJobId, pollJobUntilComplete } from "@/lib/queryClient";
import type { LambdaRequest, AnalysisResponse, JobInitResponse } from "@shared/schema";
import { useToast } from "@/hooks/use-toast";

interface LoadingViewProps {
  companyName: string;
  onAnalysisComplete: (analysis: AnalysisResponse) => void;
  onError: () => void;
}

export default function LoadingView({ companyName, onAnalysisComplete, onError }: LoadingViewProps) {
  const { toast } = useToast();
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("Initializing analysis...");
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  const analysisMutation = useMutation({
    mutationFn: async (data: LambdaRequest & { jobId?: string }) => {
      // If we have a jobId (from sessionStorage), resume polling
      if (data.jobId) {

        setStatusMessage("Resuming analysis...");
        setCurrentJobId(data.jobId);
        sessionStorage.setItem('jobId', data.jobId);
        setStatusMessage("Processing ads data...");
        
        
      }

      // Start the analysis job
      setStatusMessage("Starting new analysis...");

      const analysisResponseFromJobId = await getJobId(data);
      setCurrentJobId(analysisResponseFromJobId.jobId);
      sessionStorage.setItem('jobId', analysisResponseFromJobId.jobId);
      setStatusMessage("Processing ads data...");

      const analysisResponse = await startAnalysis({
        companyName: companyName,
        jobId: analysisResponseFromJobId.jobId
      });

      const result = await pollJobUntilComplete(
        analysisResponse,
        (progressPercent) => {
          setProgress(progressPercent);
          setStatusMessage(`Analyzing ads...`);
        }
      );

      setStatusMessage("Analysis complete!");
      return result;
    },
    onSuccess: (data) => {
      onAnalysisComplete(data);
    },
    onError: (error) => {
      toast({
        title: "Analysis Failed",
        description: error.message,
        variant: "destructive",
      });
      // Trigger error view
      onError();
    },
  });

  useEffect(() => {
    let sessionUuid = sessionStorage.getItem('sessionUuid');
    const storedJobId = sessionStorage.getItem('jobId');

    if (storedJobId && sessionUuid) {
      console.log("Resuming job with ID:", storedJobId);
      analysisMutation.mutate({
        companyName: companyName,
        sessionUuid: sessionUuid,
        jobId: storedJobId,
      });
    } else if (companyName && !analysisMutation.isPending) {
      console.log("Starting new job for company:", companyName);
      if (!sessionUuid) {
        sessionUuid = crypto.randomUUID();
        sessionStorage.setItem('sessionUuid', sessionUuid);
      }
      analysisMutation.mutate({ companyName, sessionUuid });
    }
  }, [companyName]);

  return (
    <div className="relative min-h-[calc(100vh-200px)]">
      {/* Background Effects - 5 Orbs */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0">
        {/* Grid background */}
        <div 
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px'
          }}
        />
        
        {/* 5 Gradient orbs */}
        <div 
          className="absolute rounded-full loading-orb-1"
          style={{
            width: '800px',
            height: '800px',
            background: 'radial-gradient(circle, rgba(255, 107, 53, 0.75), rgba(255, 154, 86, 0.5), transparent)',
            top: '-350px',
            right: '-250px',
            filter: 'blur(100px)',
            opacity: 0.85
          }}
        />
        <div 
          className="absolute rounded-full loading-orb-2"
          style={{
            width: '700px',
            height: '700px',
            background: 'radial-gradient(circle, rgba(255, 154, 86, 0.7), rgba(255, 167, 38, 0.45), transparent)',
            bottom: '-250px',
            left: '-150px',
            filter: 'blur(100px)',
            opacity: 0.85
          }}
        />
        <div 
          className="absolute rounded-full loading-orb-3"
          style={{
            width: '600px',
            height: '600px',
            background: 'radial-gradient(circle, rgba(255, 138, 101, 0.65), rgba(255, 183, 77, 0.4), transparent)',
            top: '40%',
            left: '60%',
            filter: 'blur(100px)',
            opacity: 0.85
          }}
        />
        <div 
          className="absolute rounded-full loading-orb-4"
          style={{
            width: '500px',
            height: '500px',
            background: 'radial-gradient(circle, rgba(255, 183, 77, 0.6), rgba(255, 138, 101, 0.35), transparent)',
            top: '20%',
            left: '10%',
            filter: 'blur(100px)',
            opacity: 0.85
          }}
        />
        <div 
          className="absolute rounded-full loading-orb-5"
          style={{
            width: '650px',
            height: '650px',
            background: 'radial-gradient(circle, rgba(255, 167, 38, 0.65), rgba(255, 107, 53, 0.4), transparent)',
            bottom: '10%',
            right: '15%',
            filter: 'blur(100px)',
            opacity: 0.85
          }}
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center px-8 py-16 max-w-[1200px] mx-auto w-full min-h-[calc(100vh-200px)]">
        {/* Hero Text */}
        <div className="text-center mb-16">
          <h1 
            className="font-semibold leading-tight mb-4"
            style={{
              fontSize: '3.5rem',
              letterSpacing: '-2px',
              color: 'white'
            }}>
            Get insights from your<br/>competitors' ads,
          </h1>
          <p 
            style={{
              fontSize: '1.2rem',
              color: 'rgba(255, 255, 255, 0.5)',
              fontWeight: 400,
              letterSpacing: '0.5px'
            }}>
            powered by AI, with just one click.
          </p>
        </div>

        {/* Loading Card */}
        <div 
          className="w-full max-w-[700px] p-12 rounded-[30px] loading-card-animation"
          style={{
            background: 'rgba(255, 255, 255, 0.02)',
            backdropFilter: 'blur(40px)',
            WebkitBackdropFilter: 'blur(40px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)'
          }}>
          
          {/* Company Name */}
          <div 
            className="mb-8"
            style={{
              fontSize: '1.1rem',
              color: 'rgba(255, 255, 255, 0.6)',
              fontWeight: 500
            }}>
            {companyName}
          </div>

          {/* Job ID Section */}
          {currentJobId && (
            <div className="mb-10">
              <div 
                style={{
                  fontSize: '0.85rem',
                  color: 'rgba(255, 255, 255, 0.5)',
                  marginBottom: '0.5rem',
                  fontWeight: 500,
                  letterSpacing: '0.5px'
                }}>
                Job ID
              </div>
              <div 
                style={{
                  fontSize: '0.9rem',
                  color: 'rgba(255, 255, 255, 0.4)',
                  fontFamily: 'Courier New, monospace',
                  wordBreak: 'break-all'
                }}>
                {currentJobId}
              </div>
            </div>
          )}

          {/* Status Section */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <div 
                className="loading-spinner"
                style={{
                  width: '20px',
                  height: '20px',
                  border: '2px solid rgba(255, 107, 53, 0.2)',
                  borderTopColor: '#ff6b35',
                  borderRadius: '50%'
                }}
              />
              <span 
                style={{
                  fontSize: '1rem',
                  color: 'white',
                  fontWeight: 500
                }}>
                {statusMessage}
              </span>
              {progress > 0 && (
                <span 
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: 600,
                    color: '#ff6b35'
                  }}>
                  {Math.round(progress)}%
                </span>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          {progress > 0 && (
            <div className="mt-4">
              <div 
                className="w-full h-2 rounded-full overflow-hidden relative"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)'
                }}>
                <div 
                  className="h-full rounded-full relative overflow-hidden transition-all duration-300"
                  style={{
                    background: 'linear-gradient(90deg, #ff6b35 0%, #ff9a56 100%)',
                    width: `${progress}%`,
                    boxShadow: '0 2px 8px rgba(255, 107, 53, 0.3)'
                  }}>
                  <div 
                    className="shimmer-effect"
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      background: 'linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent)'
                    }}
                  />
                </div>
              </div>
              <div 
                className="mt-3"
                style={{
                  fontSize: '0.9rem',
                  color: 'rgba(255, 255, 255, 0.5)'
                }}>
                {Math.round(progress)}% complete
              </div>
            </div>
          )}
        </div>
      </div>

      
    </div>
  );
}