import { Compass } from "lucide-react";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Compass className="mb-4 h-12 w-12 text-ink-600" />
      <h1 className="mb-2 text-2xl font-bold text-ink-100">Page not found</h1>
      <p className="mb-6 max-w-md text-sm text-ink-400">
        That route does not exist in the console.
      </p>
      <Link href="/" className="btn-primary">
        Back to overview
      </Link>
    </div>
  );
}
