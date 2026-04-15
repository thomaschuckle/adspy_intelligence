import { useState, useEffect, useRef } from "react";
import { Loader2, ChevronLeft, ChevronRight, X } from "lucide-react";
import type { AnalysisResponse, AdImage, AnalysisReport } from "@shared/schema";
import { pollForReport } from "@/lib/queryClient";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";

interface ResultsViewProps {
  analysis: AnalysisResponse;
  onNewAnalysis: () => void;
  onViewHistory: () => void; 
}

export default function ResultsView({ analysis, onNewAnalysis, onViewHistory }: ResultsViewProps) {
  const [selectedImage, setSelectedImage] = useState<AdImage | null>(null);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [reportData, setReportData] = useState<AnalysisReport | null>(null);
  const [reportLoading, setReportLoading] = useState(true);
  const [reportError, setReportError] = useState<string | null>(null);
  const [leftPanelWidth, setLeftPanelWidth] = useState(50);
  const [isResizing, setIsResizing] = useState(false);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const resizerRef = useRef<HTMLDivElement>(null);
  const reportContentRef = useRef<HTMLDivElement>(null);

  const availableImages = analysis.images || [];

  // Start polling for report when component mounts
  useEffect(() => {
    sessionStorage.removeItem('jobId');

    const startReportPolling = async () => {
      try {
        setReportLoading(true);
        setReportError(null);
        
        console.log('Starting report polling for:', analysis.companyName);
        
        let sessionUuid = sessionStorage.getItem('sessionUuid')!;
        const report = await pollForReport({ companyName: analysis.companyName, jobId: analysis.jobId });
        
        if (report) {
          setReportData(report);
          console.log('Report polling completed successfully');
        } else {
          setReportError('Report not available.');
          console.log('Report polling timed out');
        }
      } catch (error) {
        setReportError('Failed to fetch report. Please try again.');
        console.error('Report polling error:', error);
      } finally {
        setReportLoading(false);
      }
    };
    startReportPolling();
  }, [analysis.companyName]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedImage) return;
      
      if (e.key === 'Escape') {
        setSelectedImage(null);
      } else if (e.key === 'ArrowLeft') {
        navigateImage('prev');
      } else if (e.key === 'ArrowRight') {
        navigateImage('next');
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedImage, currentImageIndex]);

  // Resizer logic
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const offsetX = e.clientX - containerRect.left;
      const percentage = (offsetX / containerRect.width) * 100;

      if (percentage > 20 && percentage < 80) {
        setLeftPanelWidth(percentage);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    if (isResizing) {
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const openImageModal = (image: AdImage, index: number) => {
    setSelectedImage(image);
    setCurrentImageIndex(index);
  };

  const closeImageModal = () => {
    setSelectedImage(null);
  };

  const navigateImage = (direction: 'prev' | 'next') => {
    const newIndex = direction === 'prev' 
      ? (currentImageIndex - 1 + availableImages.length) % availableImages.length
      : (currentImageIndex + 1) % availableImages.length;
    
    setCurrentImageIndex(newIndex);
    setSelectedImage(availableImages[newIndex]);
  };

  const handleResizerMouseDown = () => {
    setIsResizing(true);
  };

  const handleDownloadPDF = () => {
    if (!reportData || !reportData.overview) {
      console.error("Report content not available for download");
      return;
    }
    try {
      
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
      });
            // PDF dimensions
      const pageWidth = 210;
      const pageHeight = 297;
      const margin = 20;
      const contentWidth = pageWidth - (2 * margin);
      let yPosition = margin;
      // Colors
      const orange = { r: 255, g: 107, b: 53 };
      const darkGray = { r: 30, g: 30, b: 30 };
      const mediumGray = { r: 100, g: 100, b: 100 };
      const lightGray = { r: 180, g: 180, b: 180 };
      const checkPageBreak = (requiredSpace: number) => {
        if (yPosition + requiredSpace > pageHeight - 30) {
          pdf.addPage();
          yPosition = margin;
          return true;
        }
        return false;
      };

      // Helper to clean and normalize text
      const cleanText = (text: string): string => {
        return text
          .trim()
          // Normalize Unicode characters
          .normalize('NFKD')
          // Remove zero-width spaces and other invisible characters
          .replace(/[\u200B-\u200D\uFEFF]/g, '')
          // Replace smart quotes with regular quotes
          .replace(/[\u2018\u2019]/g, "'")
          .replace(/[\u201C\u201D]/g, '"')
          // Replace em dash and en dash with regular dash
          .replace(/[\u2013\u2014]/g, '-')
          // Replace multiple spaces with single space
          .replace(/\s+/g, ' ')
          // Remove other special Unicode characters that might cause issues
          .replace(/[^\x20-\x7E\xA0-\xFF]/g, '');
      };
      // Helper to add text safely without overflow
      const addTextLine = (text: string, x: number, y: number) => {
        const cleaned = cleanText(text);
        pdf.text(cleaned, x, y, { maxWidth: contentWidth });
      };

      // HEADER - Gradient background box
      pdf.setFillColor(orange.r, orange.g, orange.b);
      pdf.rect(0, 0, pageWidth, 50, 'F');
      
      pdf.setFontSize(24);
      pdf.setFont("helvetica", "bold");
      pdf.setTextColor(255, 255, 255);
      addTextLine(analysis.companyName.toUpperCase(), margin, 25);
      
      pdf.setFontSize(14);
      pdf.setFont("helvetica", "normal");
      addTextLine("Advertising Intelligence Report", margin, 35);

      pdf.setFontSize(9);
      pdf.setTextColor(255, 255, 255);
      addTextLine(`Job ID: ${analysis.jobId}`, margin, 43);
      
      // Calculate x position for right-aligned date without using align option
      pdf.setFontSize(9);
      const dateText = `Generated: ${new Date().toLocaleDateString()}`;
      const dateWidth = pdf.getTextWidth(dateText);
      pdf.text(dateText, pageWidth - margin - dateWidth, 35);
      yPosition = 65;
      // Process markdown content
      const content = reportData.overview;
      const lines = content.split('\n');
      let inTable = false;
      let tableData: string[][] = [];
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        
        // Handle tables
        if (line.includes('|')) {
          if (!inTable) {
            inTable = true;
            tableData = [];
          }
          const cells = line.split('|').map(c => c.trim()).filter(c => c);
          if (!line.includes('---')) {
            tableData.push(cells);
          }
          continue;
        } else if (inTable) {
          // End of table, render it
          if (tableData.length > 0) {
            checkPageBreak(tableData.length * 10 + 10);
            
            const colWidth = contentWidth / tableData[0].length;
            
            // Header row
            pdf.setFillColor(orange.r, orange.g, orange.b);
            pdf.rect(margin, yPosition, contentWidth, 8, 'F');
            pdf.setFontSize(9);
            pdf.setFont("helvetica", "bold");
            pdf.setTextColor(255, 255, 255);
            
            tableData[0].forEach((cell, idx) => {
              const cellWidth = colWidth - 4;
              const cleanedCell = cleanText(cell);
              const wrappedCell = pdf.splitTextToSize(cleanedCell, cellWidth);
              pdf.text(cleanText(wrappedCell[0] || cleanedCell), margin + (idx * colWidth) + 2, yPosition + 5.5);
            });
            
            yPosition += 8;
            
            // Data rows
            pdf.setFont("helvetica", "normal");
            pdf.setTextColor(darkGray.r, darkGray.g, darkGray.b);
            pdf.setFontSize(8);
            
            for (let row = 1; row < tableData.length; row++) {
              if (row % 2 === 0) {
                pdf.setFillColor(250, 250, 250);
                pdf.rect(margin, yPosition, contentWidth, 7, 'F');
              }
              
              tableData[row].forEach((cell, idx) => {
                const cellWidth = colWidth - 4;
                const cleanedCell = cleanText(cell);
                const wrappedCell = pdf.splitTextToSize(cleanedCell, cellWidth);
                pdf.text(cleanText(wrappedCell[0] || cleanedCell), margin + (idx * colWidth) + 2, yPosition + 5);
              });
              
              yPosition += 7;
              checkPageBreak(10);
            }
            
            yPosition += 5;
          }
          inTable = false;
          tableData = [];
        }
        if (line.trim() === '') {
          yPosition += 3;
          continue;
        }
        // H4 Headers (####)
        if (line.startsWith('#### ')) {
          checkPageBreak(12);
          yPosition += 4;
          
          pdf.setFontSize(11);
          pdf.setFont("helvetica", "bold");
          pdf.setTextColor(darkGray.r, darkGray.g, darkGray.b);
          
          const h4Text = cleanText(line.replace('#### ', ''));
          const h4Lines = pdf.splitTextToSize(h4Text, contentWidth);
          h4Lines.forEach((h4Line: string, idx: number) => {
            pdf.text(cleanText(h4Line), margin, yPosition + (idx * 5));
          });
          yPosition += 7;
        }
        // Section Headers (H2 - ##)
        else if (line.startsWith('## ')) {
          checkPageBreak(20);
          yPosition += 8;
          
          // Orange accent bar
          pdf.setFillColor(orange.r, orange.g, orange.b);
          pdf.rect(margin, yPosition - 2, 4, 10, 'F');
          
          pdf.setFontSize(16);
          pdf.setFont("helvetica", "bold");
          pdf.setTextColor(darkGray.r, darkGray.g, darkGray.b);
          
          const headerText = cleanText(line.replace('## ', '')).toUpperCase();
          const headerLines = pdf.splitTextToSize(headerText, contentWidth - 10);
          headerLines.forEach((hLine: string, idx: number) => {
            pdf.text(cleanText(hLine), margin + 7, yPosition + 5 + (idx * 6));
          });
          
          yPosition += 12;
          
          // Underline
          pdf.setDrawColor(lightGray.r, lightGray.g, lightGray.b);
          pdf.setLineWidth(0.3);
          pdf.line(margin, yPosition, pageWidth - margin, yPosition);
          yPosition += 5;
          }
        // Subsection Headers (H3 - ###)
        else if (line.startsWith('### ')) {
          checkPageBreak(15);
          yPosition += 5;
          
          pdf.setFontSize(13);
          pdf.setFont("helvetica", "bold");
          pdf.setTextColor(orange.r, orange.g, orange.b);
          
          const subHeaderText = cleanText(line.replace('### ', ''));
          const subHeaderLines = pdf.splitTextToSize(subHeaderText, contentWidth);
          subHeaderLines.forEach((shLine: string, idx: number) => {
            pdf.text(cleanText(shLine), margin, yPosition + (idx * 6));
          });
          yPosition += 8;
          }
        // H1
        else if (line.startsWith('# ') && !line.startsWith('## ')) {
          checkPageBreak(18);
          yPosition += 10;
          pdf.setFontSize(18);
          pdf.setFont("helvetica", "bold");
          pdf.setTextColor(darkGray.r, darkGray.g, darkGray.b);
          
          const h1Text = cleanText(line.replace('# ', ''));
          const h1Lines = pdf.splitTextToSize(h1Text, contentWidth);
          h1Lines.forEach((h1Line: string, idx: number) => {
            pdf.text(cleanText(h1Line), margin, yPosition + (idx * 7));
          });
          yPosition += 12;
        }
        // Bold lines starting with **
        else if (line.trim().startsWith('**') && line.trim().endsWith('**')) {
          checkPageBreak(8);
          
          pdf.setFontSize(10);
          pdf.setFont("helvetica", "bold");
          pdf.setTextColor(darkGray.r, darkGray.g, darkGray.b);
          
          const boldText = cleanText(line.replace(/\*\*/g, ''));
          const lines = pdf.splitTextToSize(boldText, contentWidth);
          lines.forEach((l: string) => {
            pdf.text(cleanText(l), margin, yPosition);
            yPosition += 6;
          });
          yPosition += 2;
        }
        // Bullet  items
        else if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
          checkPageBreak(8);
          
          pdf.setFontSize(9);
          pdf.setFont("helvetica", "normal");
          pdf.setTextColor(mediumGray.r, mediumGray.g, mediumGray.b);
          
          // Bullet point
          pdf.setFillColor(orange.r, orange.g, orange.b);
          pdf.circle(margin + 2, yPosition - 1.5, 1, 'F');
          
          const listText = cleanText(line.trim().substring(2).replace(/\*\*(.*?)\*\*/g, '$1'));
          const lines = pdf.splitTextToSize(listText, contentWidth - 8);
          
          lines.forEach((l: string, idx: number) => {
            pdf.text(cleanText(l), margin + 6, yPosition);
            if (idx < lines.length - 1) yPosition += 5;
          });
          
          yPosition += 6;
        }
        // Numbered lists
        else if (line.trim().match(/^\d+\./)) {
          checkPageBreak(8);
          
          pdf.setFontSize(9);
          pdf.setFont("helvetica", "normal");
          pdf.setTextColor(mediumGray.r, mediumGray.g, mediumGray.b);
          
          const cleanedLine = cleanText(line.trim());
          const lines = pdf.splitTextToSize(cleanedLine, contentWidth - 5);
          lines.forEach((l: string) => {
            pdf.text(cleanText(l), margin + 3, yPosition);
            yPosition += 5;
          });
          yPosition += 1;
        }
        // Regular paragraphs
        else {
          checkPageBreak(10);
          
          pdf.setFontSize(9);
          pdf.setFont("helvetica", "normal");
          pdf.setTextColor(mediumGray.r, mediumGray.g, mediumGray.b);
          
          // Handle inline bold and markdown
          let processedText = line
            .replace(/\*\*(.*?)\*\*/g, '$1')  // Remove bold markers
            .replace(/\*(.*?)\*/g, '$1')       // Remove italic markers
            .replace(/`(.*?)`/g, '$1')         // Remove code markers
            .replace(/\[(.*?)\]\(.*?\)/g, '$1'); // Remove links, keep text
          
          processedText = cleanText(processedText);
          
          const lines = pdf.splitTextToSize(processedText, contentWidth);
          lines.forEach((l: string) => {
            pdf.text(cleanText(l), margin, yPosition);
            yPosition += 5;
          });
          yPosition += 1;
        }
      }
      // Footer on all pages
      const totalPages = pdf.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i);

        // Footer line
        pdf.setDrawColor(lightGray.r, lightGray.g, lightGray.b);
        pdf.setLineWidth(0.3);
        pdf.line(margin, pageHeight - 20, pageWidth - margin, pageHeight - 20);
        
        // Footer text
        pdf.setFontSize(8);
        pdf.setTextColor(mediumGray.r, mediumGray.g, mediumGray.b);
        pdf.text('AdSpy Intelligence', margin, pageHeight - 12);
        // Center page numbers without using align option
        const pageText = `Page ${i} of ${totalPages}`;
        const pageTextWidth = pdf.getTextWidth(pageText);
        pdf.text(pageText, (pageWidth - pageTextWidth) / 2, pageHeight - 12);
        
        // Right-align without using align option
        pdf.setTextColor(orange.r, orange.g, orange.b);
        const inboxWidth = pdf.getTextWidth('inbox');
        pdf.text('inbox', pageWidth - margin - inboxWidth, pageHeight - 12);
      }
      
      const fileName = `${analysis.companyName.replace(/\s+/g, "_")}_Analysis_Report.pdf`;
      pdf.save(fileName);
      console.log("PDF downloaded successfully");
    } catch (error) {
      console.error("Error generating PDF:", error);
      
    }
  };

  return (
    <div className="relative w-full">
      {/* Background Effects - 5 Orbs */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0">
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
        
        <div className="orb orb1" />
        <div className="orb orb2" />
        <div className="orb orb3" />
        <div className="orb orb4" />
        <div className="orb orb5" />
      </div>

      {/* Main Content */}
      <div className="relative z-10 w-full px-8 py-12">
        {/* Header */}
        <div className="flex justify-between items-center mb-10">
          <h1 
            style={{
              fontSize: '2rem',
              fontWeight: 600,
              letterSpacing: '-1px',
              color: 'white'
            }}>
            Analysis Results
          </h1>
          <div className="flex gap-4">
            <button 
              onClick={onViewHistory}
              className="results-btn results-btn-secondary"
              style={{
                padding: '0.8rem 1.5rem',
                borderRadius: '12px',
                fontSize: '0.9rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                border: 'none',
                background: 'rgba(255, 255, 255, 0.05)',
                backdropFilter: 'blur(20px)',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}>
              📋 HISTORY
            </button>
            <button 
              onClick={onNewAnalysis}
              className="results-btn results-btn-primary"
              style={{
                padding: '0.8rem 1.5rem',
                borderRadius: '12px',
                fontSize: '0.9rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                border: 'none',
                background: 'linear-gradient(135deg, #ff6b35 0%, #ff9a56 100%)',
                color: 'white',
                boxShadow: '0 4px 12px rgba(255, 107, 53, 0.3)'
              }}>
              New Analysis
            </button>
          </div>
        </div>

        {/* Main Grid with Resizer */}
        <div 
          ref={containerRef}
          className="flex gap-6 mb-12 relative"
          style={{ height: '600px' }}>
          
          {/* Text Report Card */}
          <div 
            className="results-card"
            style={{
              flex: `0 0 calc(${leftPanelWidth}% - 12px)`,
              minWidth: '300px',
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(40px)',
              WebkitBackdropFilter: 'blur(40px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '20px',
              padding: '2rem',
              boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)',
              height: '113%',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}>
            
            <div className="mb-6">
              <div className="flex justify-between items-center mb-2">
                <div
                  style={{
                    fontSize: "1.1rem",
                    fontWeight: 600,
                    letterSpacing: "-0.5px",
                    color: "white",
                  }}
                >
                  Text Report
                </div>
                <div
                  onClick={handleDownloadPDF}
                  className="download-icon-results"
                  style={{
                    width: "36px",
                    height: "36px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "rgba(255, 107, 53, 0.1)",
                    borderRadius: "10px",
                    cursor: "pointer",
                    transition: "all 0.3s ease",
                    fontSize: "1.2rem",
                  }}
                >
                  ⬇
                </div>
              </div>
              <div 
                style={{
                  fontSize: "0.85rem",
                  color: "rgba(255, 255, 255, 0.5)",
                  fontFamily: "monospace",
                }}>
                Job ID: {analysis.jobId}
              </div>
            </div>

            <div 
              ref={reportContentRef}
              className="report-content-scroll"
              style={{
                flex: 1,
                overflowY: 'auto',
                paddingRight: '0.5rem'
              }}>
              
              {reportLoading ? (
                <div className="flex flex-col items-center justify-center h-full space-y-4">
                  <Loader2 className="w-8 h-8 animate-spin" style={{ color: '#ff6b35' }} />
                  <div className="text-center">
                    <p style={{ fontSize: '1.1rem', fontWeight: 500, color: 'white', marginBottom: '0.5rem' }}>
                      Analyzing Report...
                    </p>
                    <p style={{ fontSize: '0.9rem', color: 'rgba(255, 255, 255, 0.5)' }}>
                      Polling S3 for analysis report. This may take up to 4 minute.
                    </p>
                  </div>
                </div>
              ) : reportError ? (
                <div className="flex flex-col items-center justify-center h-full space-y-4">
                  <div className="text-center">
                    <p style={{ fontSize: '1.1rem', fontWeight: 500, color: '#ff6b35', marginBottom: '0.5rem' }}>
                      Report Not Available
                    </p>
                    <p style={{ fontSize: '0.9rem', color: 'rgba(255, 255, 255, 0.5)' }}>
                      {reportError}
                    </p>
                  </div>
                </div>
              ) : reportData && reportData.overview && reportData.overview.trim().length > 0 ? (
                <div style={{ color: 'rgba(255, 255, 255, 0.9)' }}>
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => (
                        <h1 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '1.5rem', letterSpacing: '-0.5px', color: 'white' }}>
                          {children}
                        </h1>
                      ),
                      h2: ({ children }) => (
                        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '2rem', marginBottom: '1rem', color: 'white' }}>
                          {children}
                        </h2>
                      ),
                      h3: ({ children }) => (
                        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'white' }}>
                          {children}
                        </h3>
                      ),
                      p: ({ children }) => (
                        <p style={{ marginBottom: '0.6rem', color: 'rgba(255, 255, 255, 0.8)', fontSize: '0.9rem', lineHeight: 1.6 }}>
                          {children}
                        </p>
                      ),
                      table: ({ children }) => (
                        <div style={{ overflowX: 'auto', margin: '1rem 0' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                            {children}
                          </table>
                        </div>
                      ),
                      th: ({ children }) => (
                        <th style={{ padding: '0.6rem', textAlign: 'left', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', fontSize: '0.85rem', color: 'rgba(255, 255, 255, 0.9)', fontWeight: 600 }}>
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td style={{ padding: '0.6rem', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.9rem', color: 'rgba(255, 255, 255, 0.8)' }}>
                          {children}
                        </td>
                      ),
                      ul: ({ children }) => (
                        <ul style={{ listStyle: 'disc', listStylePosition: 'inside', marginBottom: '1rem', color: 'rgba(255, 255, 255, 0.8)' }}>
                          {children}
                        </ul>
                      ),
                      li: ({ children }) => (
                        <li style={{ marginBottom: '0.3rem', fontSize: '0.9rem' }}>{children}</li>
                      ),
                      strong: ({ children }) => (
                        <strong style={{ fontWeight: 600, color: 'white' }}>{children}</strong>
                      ),
                    }}
                  >
                    {reportData.overview}
                  </ReactMarkdown>
                </div>
              ) : (
                <div 
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: '3rem 2rem',
                    textAlign: 'center'
                  }}>
                  <div 
                    style={{
                      fontSize: '3rem',
                      marginBottom: '1rem',
                      opacity: 0.5
                    }}>
                    📄
                  </div>
                  <div 
                    style={{
                      fontSize: '1.1rem',
                      fontWeight: 500,
                      color: 'white',
                      marginBottom: '0.5rem'
                    }}>
                    No Report Available
                  </div>
                  <div 
                    style={{
                      fontSize: '0.9rem',
                      color: 'rgba(255, 255, 255, 0.5)'
                    }}>
                    No report data was found for this analysis
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Resizer */}
          <div
            ref={resizerRef}
            onMouseDown={handleResizerMouseDown}
            className="resizer-results"
            style={{
              width: '4px',
              background: 'rgba(255, 255, 255, 0.1)',
              cursor: 'col-resize',
              position: 'absolute',
              height: '113%',
              left: `${leftPanelWidth}%`,
              transform: 'translateX(-50%)',
              zIndex: 10,
              transition: isResizing ? 'none' : 'background 0.2s ease'
            }}
          />

          {/* Analyzed Ads Card */}
          <div 
            className="results-card"
            style={{
              flex: 1,
              minWidth: '300px',
              background: 'rgba(255, 255, 255, 0.02)',
              backdropFilter: 'blur(40px)',
              WebkitBackdropFilter: 'blur(40px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '20px',
              padding: '2rem',
              boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)',
              height: '113%',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}>
            
            <div className="flex justify-between items-center mb-6">
              <div 
                style={{
                  fontSize: '1.1rem',
                  fontWeight: 600,
                  letterSpacing: '-0.5px',
                  color: 'white'
                }}>
                Analyzed Ads
              </div>
              <button 
                className="filter-btn-results"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.6rem 1.2rem',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '10px',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  color: 'white'
                }}>
                🔍 Filter
              </button>
            </div>

            <div 
              className="ads-grid-scroll"
              style={{
                flex: 1,
                overflowY: 'auto',
                paddingRight: '0.5rem',
                columnCount: availableImages.length > 0 ? 3 : 1,
                columnGap: '1rem'
              }}>
              
              {availableImages.length > 0 ? availableImages.map((image, i) => (
                <div
                  key={image.id}
                  onClick={() => openImageModal(image, i)}
                  className="ad-thumbnail-results"
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    marginBottom: '1rem',
                    breakInside: 'avoid',
                    display: 'inline-block',
                    width: '100%'
                  }}>
                  <img 
                    src={image.thumbnail || image.url} 
                    alt={image.caption}
                    style={{
                      width: '100%',
                      height: 'auto',
                      display: 'block'
                    }}
                    loading="lazy"
                  />
                </div>
              )) : (
                <div 
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: '3rem 2rem',
                    textAlign: 'center'
                  }}>
                  <div 
                    style={{
                      fontSize: '3rem',
                      marginBottom: '1rem',
                      opacity: 0.5
                    }}>
                    📭
                  </div>
                  <div 
                    style={{
                      fontSize: '1.1rem',
                      fontWeight: 500,
                      color: 'white',
                      marginBottom: '0.5rem'
                    }}>
                    No Ad Images Available
                  </div>
                  <div 
                    style={{
                      fontSize: '0.9rem',
                      color: 'rgba(255, 255, 255, 0.5)'
                    }}>
                    No ad images were found for this analysis
                  </div>
                </div>
              )}
          </div>

            <div 
              style={{
                fontSize: '0.85rem',
                color: 'rgba(255, 255, 255, 0.5)',
                marginTop: '1rem'
              }}>
              {availableImages.length} ads analyzed and processed
            </div>
          </div>
        </div>

        
      </div>

      {/* Image Lightbox Modal */}
      {selectedImage && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50 p-4"
          onClick={closeImageModal}
        >
          <div className="relative max-w-7xl max-h-full flex items-center justify-center">
            {/* Close Button */}
            <button
              onClick={closeImageModal}
              className="absolute top-4 right-4 z-10 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full p-2 transition-all"
            >
              <X className="w-6 h-6 text-white" />
            </button>

            {/* Previous Button */}
            {availableImages.length > 1 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  navigateImage('prev');
                }}
                className="absolute left-4 top-1/2 -translate-y-1/2 z-10 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full p-3 transition-all"
              >
                <ChevronLeft className="w-8 h-8 text-white" />
              </button>
            )}

            {/* Next Button */}
            {availableImages.length > 1 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  navigateImage('next');
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 z-10 bg-white bg-opacity-20 hover:bg-opacity-30 rounded-full p-3 transition-all"
              >
                <ChevronRight className="w-8 h-8 text-white" />
              </button>
            )}

            {/* Main Image */}
            <div 
              className="relative"
              onClick={(e) => e.stopPropagation()}
            >
              <img
                src={selectedImage?.url}
                alt={selectedImage?.caption}
                className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
                style={{ maxWidth: '90vw' }}
              />
              
              {/* Image Info Overlay */}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black to-transparent p-6 rounded-b-lg">
                <div className="text-white">
                  <h3 className="text-xl font-semibold mb-2">{selectedImage?.caption}</h3>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      {selectedImage?.adNumber && (
                        <span className="bg-gray-600 bg-opacity-80 px-3 py-1 rounded-full text-sm">
                          Ad #{selectedImage?.adNumber}
                        </span>
                      )}
                    </div>
                    {availableImages.length > 1 && (
                      <span className="text-sm opacity-75">
                        {currentImageIndex + 1} of {availableImages.length}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      
    </div>
  );
}