import { useState } from "react";

interface HistoryViewProps {
  onLoadHistory: (jobId: string) => void;
}

export default function HistoryView({ onLoadHistory }: HistoryViewProps) {
  const [jobId, setJobId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (jobId.trim()) {
      onLoadHistory(jobId.trim());
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-200px)]">
      {/* Background Effects */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0">
        {/* Grid background */}
        <div 
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255, 154, 86, 0.03) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255, 154, 86, 0.03) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px'
          }}
        />
        
        {/* Gradient orbs */}
        <div 
          className="absolute rounded-full orb-float-1"
          style={{
            width: '900px',
            height: '900px',
            background: 'radial-gradient(circle, #ff6b35, transparent)',
            top: '-400px',
            right: '-300px',
            filter: 'blur(120px)',
            opacity: 0.6
          }}
        />
        <div 
          className="absolute rounded-full orb-float-2"
          style={{
            width: '800px',
            height: '800px',
            background: 'radial-gradient(circle, #ff9a56, transparent)',
            bottom: '-300px',
            left: '-200px',
            filter: 'blur(120px)',
            opacity: 0.6
          }}
        />
        <div 
          className="absolute rounded-full orb-float-3"
          style={{
            width: '700px',
            height: '700px',
            background: 'radial-gradient(circle, #ffa726, transparent)',
            top: '30%',
            left: '50%',
            filter: 'blur(120px)',
            opacity: 0.6
          }}
        />
      </div>

      {/* Hero Section */}
      <section className="relative z-10 max-w-[1200px] mx-auto px-16 pt-32 pb-20 text-center flex flex-col items-center justify-center" style={{ minHeight: 'calc(100vh - 200px)' }}>
        
        <p 
          className="mb-16 fade-in-up-delay-animation"
          style={{
            fontSize: '1.3rem',
            color: 'rgba(255, 255, 255, 0.5)',
            fontWeight: 400,
            letterSpacing: '0.5px'
          }}>
          Enter your Job ID to retrieve past analysis results
        </p>

        {/* Job ID Input Container */}
        <div className="max-w-[800px] w-full fade-in-up-delay-2-animation">
          <div 
            className="search-wrapper-glass p-2.5 rounded-[20px] transition-all duration-300"
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = 'rgba(255, 154, 86, 0.4)';
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
              e.currentTarget.style.boxShadow = '0 0 0 4px rgba(255, 154, 86, 0.1)';
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
              e.currentTarget.style.boxShadow = 'none';
            }}>
            <form onSubmit={handleSubmit} className="flex gap-3 items-center">
              <input
                type="text"
                placeholder="Enter Job ID..."
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                maxLength={100}
                className="flex-1 border-none outline-none px-6 py-5 text-white bg-transparent"
                style={{
                  fontSize: '1.05rem',
                  fontFamily: 'Avenir, sans-serif'
                }}
                required
              />
              <button
                type="submit"
                className="px-10 py-5 rounded-[14px] font-semibold transition-all duration-300 hover:-translate-y-0.5"
                style={{
                  background: 'linear-gradient(135deg, #ff6b35 0%, #ff9a56 100%)',
                  color: 'white',
                  fontSize: '1rem',
                  fontWeight: 600,
                  letterSpacing: '0.3px',
                  boxShadow: '0 8px 24px rgba(255, 107, 53, 0.3)',
                  border: 'none',
                  cursor: 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = '0 12px 32px rgba(255, 107, 53, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = '0 8px 24px rgba(255, 107, 53, 0.3)';
                }}>
                Load History
              </button>
            </form>
          </div>
        </div>
      </section>

      
    </div>
  );
}