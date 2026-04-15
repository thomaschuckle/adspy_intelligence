interface HeaderProps {
  onNavigateHome: () => void;
  onNavigateHistory: () => void;
}

export default function Header({ onNavigateHome, onNavigateHistory }: HeaderProps) {
  return (
    <nav 
      className="relative z-[100] px-16 py-8 flex justify-between items-center"
      style={{
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
      }}>
      <div className="flex items-center gap-2" style={{ fontSize: '1.5rem', fontWeight: 600 }}>
        <div 
          className="w-2 h-2 rounded-full"
          style={{
            background: 'linear-gradient(135deg, #ff6b35, #ff9a56)',
            boxShadow: '0 0 20px rgba(255, 154, 86, 0.6)'
          }}
        />
        <span>inbox</span>
      </div>
      <div className="hidden md:flex gap-12">
        <a 
          onClick={(e) => {
            e.preventDefault();
            onNavigateHome();
          }}
          href="#dashboard" 
          className="transition-colors duration-300"
          style={{
            color: 'rgba(255, 255, 255, 0.6)',
            fontSize: '0.95rem',
            fontWeight: 500,
            letterSpacing: '0.5px',
            textDecoration: 'none',
            cursor: 'pointer'
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#ff9a56'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'rgba(255, 255, 255, 0.6)'}>
          Home
        </a>
        <a 
          onClick={(e) => {
            e.preventDefault();
            onNavigateHistory();
          }}
          href="#analytics" 
          className="transition-colors duration-300"
          style={{
            color: 'rgba(255, 255, 255, 0.6)',
            fontSize: '0.95rem',
            fontWeight: 500,
            letterSpacing: '0.5px',
            textDecoration: 'none',
            cursor: 'pointer'
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#ff9a56'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'rgba(255, 255, 255, 0.6)'}>
          History
        </a>
        <a 
          href="#history" 
          className="transition-colors duration-300"
          style={{
            color: 'rgba(255, 255, 255, 0.6)',
            fontSize: '0.95rem',
            fontWeight: 500,
            letterSpacing: '0.5px',
            textDecoration: 'none'
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#ff9a56'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'rgba(255, 255, 255, 0.6)'}>
          Contact
        </a>
      </div>
    </nav>
  );
}