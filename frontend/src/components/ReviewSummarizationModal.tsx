import { Alert, Modal, ModalVariant } from '@patternfly/react-core';
import {
  useProductReviews,
  useProductReviewSummarization,
} from '../hooks/useReviews';

// Function to format the AI summary text with proper styling
const formatSummaryText = (text: string) => {
  if (!text) return '';

  // Split by lines and process each line
  const lines = text.split('\n');
  const formattedLines = lines.map((line, index) => {
    const trimmedLine = line.trim();

    // Handle **text:** as section titles (bold text with colon)
    if (trimmedLine.startsWith('**') && trimmedLine.endsWith(':')) {
      const title = trimmedLine.slice(2, -1); // Remove ** and :
      return (
        <div
          key={index}
          style={{
            fontSize: '1.3rem',
            fontWeight: '700',
            marginTop: index > 0 ? '1.5rem' : '0',
            marginBottom: '0.8rem',
            textShadow: '0 2px 4px rgba(0,0,0,0.2)',
            borderBottom: '2px solid rgba(255,255,255,0.3)',
            paddingBottom: '0.5rem',
          }}
        >
          {title}
        </div>
      );
    }

    // Handle **text** as titles (bold text without colon)
    if (trimmedLine.startsWith('**') && trimmedLine.endsWith('**')) {
      const title = trimmedLine.slice(2, -2);
      return (
        <div
          key={index}
          style={{
            fontSize: '1.3rem',
            fontWeight: '700',
            marginTop: index > 0 ? '1.5rem' : '0',
            marginBottom: '0.8rem',
            textShadow: '0 2px 4px rgba(0,0,0,0.2)',
            borderBottom: '2px solid rgba(255,255,255,0.3)',
            paddingBottom: '0.5rem',
          }}
        >
          {title}
        </div>
      );
    }

    // Handle bullet points (- text)
    if (trimmedLine.startsWith('- ')) {
      const bulletText = trimmedLine.slice(2);
      return (
        <div
          key={index}
          style={{
            marginLeft: '1rem',
            marginBottom: '0.5rem',
            position: 'relative',
            paddingLeft: '1.5rem',
          }}
        >
          <span
            style={{
              position: 'absolute',
              left: '0',
              top: '0.3rem',
              width: '6px',
              height: '6px',
              backgroundColor: 'rgba(255,255,255,0.8)',
              borderRadius: '50%',
            }}
          />
          {formatInlineText(bulletText)}
        </div>
      );
    }

    // Handle regular paragraphs
    if (trimmedLine.length > 0) {
      return (
        <div
          key={index}
          style={{
            marginBottom: '0.8rem',
            lineHeight: '1.6',
          }}
        >
          {formatInlineText(trimmedLine)}
        </div>
      );
    }

    // Empty lines
    return <div key={index} style={{ height: '0.5rem' }} />;
  });

  return <div>{formattedLines}</div>;
};

// Function to format inline text with bold formatting
const formatInlineText = (text: string) => {
  // Split text by **text** patterns and format accordingly
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      // This is bold text
      const boldText = part.slice(2, -2);
      return (
        <span
          key={index}
          style={{
            fontWeight: '700',
            textShadow: '0 1px 2px rgba(0,0,0,0.2)',
          }}
        >
          {boldText}
        </span>
      );
    }
    return part;
  });
};

interface ReviewSummarizationModalProps {
  productId: string;
  isOpen: boolean;
  onClose: () => void;
  enabled?: boolean;
}

export const ReviewSummarizationModal = ({
  productId,
  isOpen,
  onClose,
  enabled = false,
}: ReviewSummarizationModalProps) => {
  // Reviews data for context
  const reviewsQuery = useProductReviews(productId);
  const summarizationQuery = useProductReviewSummarization(productId, enabled);

  return (
    <Modal
      variant={ModalVariant.large}
      title='✨ AI Review Summary'
      isOpen={isOpen}
      onClose={onClose}
      aria-describedby='review-summarization-description'
    >
      <div
        id='review-summarization-description'
        style={{
          maxHeight: 'calc(80vh - 120px)',
          overflowY: 'auto',
          paddingRight: '24px',
        }}
      >
        {summarizationQuery.isLoading ? (
          <div
            style={{
              textAlign: 'center',
              padding: '3rem 2rem',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: '12px',
              margin: '1rem 0',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                marginBottom: '2rem',
              }}
            >
              <div
                style={{
                  width: '60px',
                  height: '60px',
                  border: '4px solid rgba(255,255,255,0.3)',
                  borderTop: '4px solid #ffffff',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  marginRight: '1rem',
                }}
              />
              <div>
                <h3
                  style={{
                    margin: 0,
                    color: '#ffffff',
                    fontSize: '1.5rem',
                    fontWeight: '600',
                  }}
                >
                  AI is analyzing reviews...
                </h3>
                <p
                  style={{
                    margin: '0.5rem 0 0 0',
                    color: 'rgba(255,255,255,0.9)',
                    fontSize: '1rem',
                  }}
                >
                  🤖 Processing customers feedback
                </p>
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                gap: '0.5rem',
              }}
            >
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  backgroundColor: '#ffffff',
                  borderRadius: '50%',
                  animation: 'pulse 1.5s ease-in-out infinite',
                }}
              />
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  backgroundColor: '#ffffff',
                  borderRadius: '50%',
                  animation: 'pulse 1.5s ease-in-out infinite 0.2s',
                }}
              />
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  backgroundColor: '#ffffff',
                  borderRadius: '50%',
                  animation: 'pulse 1.5s ease-in-out infinite 0.4s',
                }}
              />
            </div>
          </div>
        ) : summarizationQuery.error ? (
          <Alert variant='danger' isInline title='Error Generating Summary'>
            Sorry, there was an error generating the summary. Please try again.
          </Alert>
        ) : summarizationQuery.data ? (
          <div style={{ padding: '0' }}>
            <div
              style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                padding: '1.5rem',
                borderRadius: '12px',
                marginBottom: '1.5rem',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: '-50%',
                  right: '-50%',
                  width: '200%',
                  height: '200%',
                  background:
                    'radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)',
                  animation: 'float 6s ease-in-out infinite',
                }}
              />
              <div style={{ position: 'relative', zIndex: 1 }}>
                <h3
                  style={{
                    margin: '0 0 1rem 0',
                    fontSize: '1.5rem',
                    fontWeight: '600',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                >
                  ✨ AI Summary Generated
                </h3>
                <div
                  style={{
                    whiteSpace: 'pre-wrap',
                    lineHeight: '1.8',
                    fontSize: '1.1rem',
                    fontWeight: '400',
                    textShadow: '0 1px 2px rgba(0,0,0,0.1)',
                  }}
                >
                  {formatSummaryText(summarizationQuery.data.summary)}
                </div>
              </div>
            </div>

            <div
              style={{
                background: 'linear-gradient(135deg, #5a8dee 0%, #1976d2 100%)',
                padding: '1rem',
                borderRadius: '8px',
                border: 'none',
                fontSize: '0.9rem',
                color: '#ffffff',
                textAlign: 'center',
              }}
            >
              💡 This summary was generated by AI analyzing{' '}
              {reviewsQuery.data?.length || 0} customer reviews
            </div>
          </div>
        ) : (
          <Alert variant='info' isInline title='Ready to Summarize'>
            Click the "AI Summarize ✨" button to generate an AI-powered summary
            of all reviews for this product.
          </Alert>
        )}
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 0.4;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.2);
          }
        }

        @keyframes float {
          0%, 100% { transform: translate(0, 0) rotate(0deg); }
          33% { transform: translate(30px, -30px) rotate(120deg); }
          66% { transform: translate(-20px, 20px) rotate(240deg); }
        }
      `}</style>
    </Modal>
  );
};
