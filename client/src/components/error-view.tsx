import { useState } from "react";

interface ErrorViewProps {
  onBackHome: () => void;
}

export default function ErrorView({ onBackHome }: ErrorViewProps) {
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

      {/* Error Section */}
      <section className="relative z-10 max-w-[1200px] mx-auto px-16 text-center flex flex-col items-center justify-center" style={{ minHeight: 'calc(100vh - 200px)' }}>
        
        <div 
          className="text-[8rem] mb-6 fade-in-animation"
          style={{
            fontWeight: 600,
            letterSpacing: '-4px'
          }}>
          <span 
            style={{
              background: 'linear-gradient(135deg, #ff6b35 0%, #ff9a56 50%, #ffa726 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
            Oops!
          </span>
        </div>

        <h1 
          className="font-semibold leading-tight mb-6 fade-in-up-animation"
          style={{
            fontSize: '3rem',
            letterSpacing: '-2px',
            color: 'white'
          }}>
          Something went wrong
        </h1>

        <p 
          className="mb-12 fade-in-up-delay-animation"
          style={{
            fontSize: '1.2rem',
            color: 'rgba(255, 255, 255, 0.5)',
            fontWeight: 400,
            letterSpacing: '0.5px',
            maxWidth: '600px'
          }}>
          We encountered an unexpected error. Please try again or return to the homepage.
        </p>

        <button
          onClick={onBackHome}
          className="px-10 py-5 rounded-[14px] font-semibold transition-all duration-300 hover:-translate-y-0.5 fade-in-up-delay-2-animation"
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
          Back to Home
        </button>
      </section>

      
    </div>
  );
}