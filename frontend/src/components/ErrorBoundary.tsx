import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error('[ErrorBoundary]', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="grid h-screen place-items-center p-6">
          <div className="max-w-md rounded-xl border border-bad/30 bg-bad/5 p-6 text-center">
            <h1 className="text-lg font-bold text-bad">Something broke</h1>
            <p className="mt-2 text-sm text-muted">{this.state.error.message}</p>
            <button
              className="btn-primary mt-4"
              onClick={() => { this.setState({ error: null }); window.location.reload(); }}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}