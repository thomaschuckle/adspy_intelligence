import { useState, useEffect } from "react";
import Header from "@/components/header";
import Footer from "@/components/footer";
import SearchView from "@/components/search-view";
import LoadingView from "@/components/loading-view";
import ResultsView from "@/components/results-view";
import HistoryView from "@/components/history-view";
import HistoryResultView from "@/components/historyresult-view";
import ErrorView from "@/components/error-view";
import type { AnalysisResponse } from "@shared/schema";

export default function Home() {
  const [currentView, setCurrentView] = useState<"search" | "loading" | "results" | "history" | "historyResult" | "error">(() => {
    return sessionStorage.getItem("currentView") as "search" | "loading" | "results" | "history" | "historyResult" | "error" || "search";
  });

  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisResponse | null>(() => {
    const stored = sessionStorage.getItem("currentAnalysis");
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (e) {
        console.error("Failed to parse stored analysis:", e);
        return null;
      }
    }
    return null;
  });
  
  const [searchQuery, setSearchQuery] = useState(() => {
    return sessionStorage.getItem("searchQuery") || "";
  });

  const [historyJobId, setHistoryJobId] = useState<string>("");

  useEffect(() => {
    sessionStorage.setItem("currentView", currentView);
    sessionStorage.setItem("searchQuery", searchQuery);
    
    // Persist analysis data
    if (currentAnalysis) {
      sessionStorage.setItem("currentAnalysis", JSON.stringify(currentAnalysis));
    } else {
      sessionStorage.removeItem("currentAnalysis");
    }
  }, [currentView, searchQuery, currentAnalysis]);

  const handleStartAnalysis = (companyName: string) => {
    setSearchQuery(companyName);
    setCurrentView("loading");
  };

  const handleAnalysisComplete = (analysis: AnalysisResponse) => {
    setCurrentAnalysis(analysis);
    setCurrentView("results");
  };

  const handleNewAnalysis = () => {
    setCurrentView("search");
    setCurrentAnalysis(null);
    setSearchQuery("");
    sessionStorage.removeItem("currentAnalysis");
  };

  const handleViewHistory = () => {
    setCurrentView("history");
  };

  const handleNavigateHome = () => {
    setCurrentView("search");
    setCurrentAnalysis(null);
    setSearchQuery("");
    sessionStorage.removeItem("currentAnalysis");
  };

  const handleLoadHistory = async (jobId: string) => {
    // Navigate directly to history result view with the jobId
    setHistoryJobId(jobId);
    setCurrentView("historyResult");
  };

  const handleError = () => {
    setCurrentView("error");
  };

  const handleBackHome = () => {
    setCurrentView("search");
    setCurrentAnalysis(null);
    setSearchQuery("");
    sessionStorage.removeItem("currentAnalysis");
  };

  return (
    <div 
      className="min-h-screen flex flex-col relative overflow-x-hidden"
      style={{ background: '#0a0a0a', color: 'white' }}>
      {/* Noise texture overlay */}
      <div 
        className="fixed top-0 left-0 w-full h-full pointer-events-none z-[1]"
        style={{
          opacity: 0.03,
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' /%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' /%3E%3C/svg%3E")`
        }}
      />

      <Header onNavigateHome={handleNavigateHome} onNavigateHistory={handleViewHistory} />
      
      <main className="flex-1 w-full relative z-[2]">
        {currentView === "search" && (
          <SearchView onStartAnalysis={handleStartAnalysis} />
        )}
        
        {currentView === "loading" && (
          <LoadingView 
            companyName={searchQuery}
            onAnalysisComplete={handleAnalysisComplete}
            onError={handleError}
          />
        )}
        
        {currentView === "results" && (
          currentAnalysis ? (
            <ResultsView 
              analysis={currentAnalysis}
              onNewAnalysis={handleNewAnalysis}
              onViewHistory={handleViewHistory}
            />
          ) : (
            <SearchView onStartAnalysis={handleStartAnalysis} />
          )
        )}

        {currentView === "history" && (
          <HistoryView onLoadHistory={handleLoadHistory} />
        )}

        {currentView === "historyResult" && historyJobId && (
          <HistoryResultView 
            jobId={historyJobId}
            onNewAnalysis={handleNewAnalysis}
            onViewHistory={handleViewHistory}
          />
        )}

        {currentView === "error" && (
          <ErrorView onBackHome={handleBackHome} />
        )}
      </main>

      <Footer />
    </div>
  );
}