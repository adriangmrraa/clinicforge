import { Component, type ReactNode, type ErrorInfo } from 'react';
import { useTranslation } from '../context/LanguageContext';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundaryInner extends Component<Props & { t: (key: string) => string }, State> {
  constructor(props: Props & { t: (key: string) => string }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo);

    // Sentry integration (if available)
    try {
      const Sentry = (window as any).__SENTRY__;
      if (Sentry?.captureException) {
        Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
      }
    } catch {
      // Sentry not available — silent
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const { t } = this.props;
      const isDev = import.meta.env.DEV;

      return (
        <div className="min-h-screen bg-[#06060e] flex items-center justify-center p-4">
          <div className="bg-[#0d1117] border border-white/[0.06] rounded-2xl p-8 max-w-md w-full text-center">
            <div className="text-4xl mb-4">⚠</div>
            <h1 className="text-white text-xl font-semibold mb-2">
              {t('errorBoundary.title')}
            </h1>
            <p className="text-white/50 mb-6">
              {t('errorBoundary.description')}
            </p>
            {isDev && this.state.error && (
              <pre className="text-red-400/70 text-xs text-left bg-white/[0.04] p-3 rounded-lg mb-4 overflow-auto max-h-32">
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={this.handleRetry}
              className="bg-white text-[#0a0e1a] px-6 py-2.5 rounded-lg font-medium hover:bg-white/90 transition-colors"
            >
              {t('errorBoundary.retry')}
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Wrapper to inject useTranslation hook into class component
export default function ErrorBoundary({ children, fallback }: Props) {
  const { t } = useTranslation();
  return (
    <ErrorBoundaryInner t={t} fallback={fallback}>
      {children}
    </ErrorBoundaryInner>
  );
}
