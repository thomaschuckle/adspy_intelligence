export default function Footer() {
  return (
    <footer 
      className="relative z-10 px-16 py-16 text-center"
      style={{
        backdropFilter: 'blur(20px)',
        borderTop: '1px solid rgba(255, 255, 255, 0.05)'
      }}>
      <h4 className="text-lg mb-3 font-semibold">Inbox Communication</h4>
      <p style={{ color: 'rgba(255, 255, 255, 0.4)', fontSize: '0.9rem', margin: '0.3rem 0' }}>
        inbox@communication
      </p>
      <p style={{ color: 'rgba(255, 255, 255, 0.4)', fontSize: '0.9rem', margin: '0.3rem 0' }}>
        © 2025 All rights reserved
      </p>
    </footer>
  );
}