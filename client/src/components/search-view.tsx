import { useState } from "react";

interface SearchViewProps {
  onStartAnalysis: (companyName: string) => void;
}

export default function SearchView({ onStartAnalysis }: SearchViewProps) {
  const [companyName, setCompanyName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (companyName.trim()) {
      onStartAnalysis(companyName.trim());
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
        
        {/* Gradient orbs 
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
        />*/}
      </div>
      <div className="orb orb1" />
      <div className="orb orb2" />
      <div className="orb orb3" />
      <div className="orb orb4" />
      <div className="orb orb5" />
      {/* Hero Section */}
      <section className="relative z-10 max-w-[1200px] mx-auto px-16 pt-32 pb-20 text-center">
        <div 
          className="inline-flex items-center gap-2 px-5 py-2 mb-8 rounded-full fade-in-animation"
          style={{
            background: 'rgba(255, 154, 86, 0.1)',
            border: '1px solid rgba(255, 154, 86, 0.2)',
            fontSize: '0.85rem',
            fontWeight: 500,
            color: '#ff9a56'
          }}>
          <div 
            className="w-2 h-2 rounded-full pulse-dot-animation"
            style={{ background: '#ff6b35' }}
          />
          <span>AI-Powered Intelligence</span>
        </div>

        <h1 
          className="font-semibold leading-tight mb-6 fade-in-up-animation"
          style={{
            fontSize: '5.5rem',
            letterSpacing: '-3px'
          }}>
          Decode your<br/>
          <span 
            className="gradient-text"
            style={{
              background: 'linear-gradient(135deg, #ff6b35 0%, #ff9a56 50%, #ffa726 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
            competitors' strategy
          </span>
        </h1>

        <p 
          className="mb-16 fade-in-up-delay-animation"
          style={{
            fontSize: '1.3rem',
            color: 'rgba(255, 255, 255, 0.5)',
            fontWeight: 400,
            letterSpacing: '0.5px'
          }}>
          Real-time ad intelligence that gives you the edge
        </p>

        {/* Search Container */}
        <div className="max-w-[800px] mx-auto mb-32 fade-in-up-delay-2-animation">
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
                placeholder="Enter competitor name (max 50 characters)..."
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                maxLength={50}
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
                Analyze Now
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* Bento Grid Features */}
      <section className="relative z-10 max-w-[1300px] mx-auto px-16 pb-32 grid grid-cols-12 gap-6">
        {/* Feature Card 1 */}
        <div className="col-span-4 feature-card-animation" style={{ animationDelay: '0.6s' }}>
          <div 
            className="feature-card-hover p-10 rounded-[24px] transition-all duration-500 relative overflow-hidden"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
            <div 
              className="feature-icon text-[2.5rem] mb-6 transition-all duration-300"
              style={{ filter: 'grayscale(1) brightness(1.2)' }}>
              🧠
            </div>
            <h3 className="text-[1.3rem] mb-3 font-semibold" style={{ letterSpacing: '-0.5px' }}>
              AI Analysis
            </h3>
            <p style={{ color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.6, fontSize: '0.95rem', letterSpacing: '0.3px' }}>
              Deep learning algorithms decode advertising patterns and strategies in real-time
            </p>
          </div>
        </div>

        {/* Feature Card 2 */}
        <div className="col-span-4 feature-card-animation" style={{ animationDelay: '0.7s' }}>
          <div 
            className="feature-card-hover p-10 rounded-[24px] transition-all duration-500 relative overflow-hidden"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
            <div 
              className="feature-icon text-[2.5rem] mb-6 transition-all duration-300"
              style={{ filter: 'grayscale(1) brightness(1.2)' }}>
              ⚡
            </div>
            <h3 className="text-[1.3rem] mb-3 font-semibold" style={{ letterSpacing: '-0.5px' }}>
              Instant Insights
            </h3>
            <p style={{ color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.6, fontSize: '0.95rem', letterSpacing: '0.3px' }}>
              Get comprehensive competitive analysis in seconds, not days
            </p>
          </div>
        </div>

        {/* Feature Card 3 */}
        <div className="col-span-4 feature-card-animation" style={{ animationDelay: '0.8s' }}>
          <div 
            className="feature-card-hover p-10 rounded-[24px] transition-all duration-500 relative overflow-hidden"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
            <div 
              className="feature-icon text-[2.5rem] mb-6 transition-all duration-300"
              style={{ filter: 'grayscale(1) brightness(1.2)' }}>
              📊
            </div>
            <h3 className="text-[1.3rem] mb-3 font-semibold" style={{ letterSpacing: '-0.5px' }}>
              Visual Data
            </h3>
            <p style={{ color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.6, fontSize: '0.95rem', letterSpacing: '0.3px' }}>
              Beautiful dashboards that make complex data easy to understand
            </p>
          </div>
        </div>

        {/* Feature Card 4 */}
        <div className="col-span-6 feature-card-animation" style={{ animationDelay: '0.9s' }}>
          <div 
            className="feature-card-hover p-10 rounded-[24px] transition-all duration-500 relative overflow-hidden"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
            <div 
              className="feature-icon text-[2.5rem] mb-6 transition-all duration-300"
              style={{ filter: 'grayscale(1) brightness(1.2)' }}>
              📈
            </div>
            <h3 className="text-[1.3rem] mb-3 font-semibold" style={{ letterSpacing: '-0.5px' }}>
              Trend Tracking
            </h3>
            <p style={{ color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.6, fontSize: '0.95rem', letterSpacing: '0.3px' }}>
              Monitor advertising shifts and seasonal patterns with historical data analysis
            </p>
          </div>
        </div>

        {/* Feature Card 5 */}
        <div className="col-span-6 feature-card-animation" style={{ animationDelay: '1s' }}>
          <div 
            className="feature-card-hover p-10 rounded-[24px] transition-all duration-500 relative overflow-hidden"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
            <div 
              className="feature-icon text-[2.5rem] mb-6 transition-all duration-300"
              style={{ filter: 'grayscale(1) brightness(1.2)' }}>
              🔒
            </div>
            <h3 className="text-[1.3rem] mb-3 font-semibold" style={{ letterSpacing: '-0.5px' }}>
              Enterprise Security
            </h3>
            <p style={{ color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.6, fontSize: '0.95rem', letterSpacing: '0.3px' }}>
              Bank-level encryption keeps your competitive research completely private
            </p>
          </div>
        </div>

        {/* Feature Card 6 */}
        <div className="col-span-12 feature-card-animation" style={{ animationDelay: '1.1s' }}>
          <div 
            className="feature-card-hover p-10 rounded-[24px] transition-all duration-500 relative overflow-hidden flex items-center gap-12"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
            <div className="flex-1">
              <div 
                className="feature-icon text-[2.5rem] mb-6 transition-all duration-300"
                style={{ filter: 'grayscale(1) brightness(1.2)' }}>
                🔄
              </div>
              <h3 className="text-[1.3rem] mb-3 font-semibold" style={{ letterSpacing: '-0.5px' }}>
                Live Updates
              </h3>
              <p style={{ color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.6, fontSize: '0.95rem', letterSpacing: '0.3px' }}>
                Continuous monitoring ensures you never miss a competitor's move. Get alerts the moment new campaigns launch.
              </p>
            </div>
          </div>
        </div>
      </section>

      
    </div>
  );
}