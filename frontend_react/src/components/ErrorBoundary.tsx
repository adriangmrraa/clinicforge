import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

// Hardcoded strings — ErrorBoundary must work WITHOUT any context provider
// because it wraps the entire app tree (including LanguageProvider)
const STRINGS = {
  title: 'Algo salió mal',
  description: 'Ocurrió un error inesperado. Podés intentar de nuevo o contactar al soporte si el problema persiste.',
  retry: 'Reintentar',
};

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo);

    try {
      const Sentry = (window as any).__SENTRY__;
      if (Sentry?.captureException) {
        Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
      }
    } catch {
      // Sentry not available
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      const isDev = import.meta.env.DEV;

      return (
        <div className="min-h-screen bg-[#06060e] flex items-center justify-center p-4">
          <div className="bg-[#0d1117] border border-white/[0.06] rounded-2xl p-8 max-w-md w-full text-center">
            <div className="text-4xl mb-4">⚠</div>
            <h1 className="text-white text-xl font-semibold mb-2">
              {STRINGS.title}
            </h1>
            <p className="text-white/50 mb-6">
              {STRINGS.description}
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
              {STRINGS.retry}
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
