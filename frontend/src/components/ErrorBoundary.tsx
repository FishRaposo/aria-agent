"use client";

import { AlertTriangle } from "lucide-react";
import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="mx-auto my-12 flex max-w-lg flex-col items-center justify-center rounded-xl border border-rose-500/30 bg-rose-500/5 p-8 text-center">
          <AlertTriangle className="mb-4 h-10 w-10 text-rose-400" />
          <h2 className="mb-2 text-lg font-semibold text-rose-200">
            Something went wrong
          </h2>
          <p className="mb-4 max-w-md text-sm text-rose-300/80">
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          <button
            onClick={this.handleRetry}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-700"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
