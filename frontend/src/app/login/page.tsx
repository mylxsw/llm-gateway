/**
 * Login Page (Server)
 * Wrap client component with Suspense for search params.
 */

import { Suspense } from 'react';
import { LoginClient } from './LoginClient';

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6 text-sm text-muted-foreground">
          Loading...
        </div>
      }
    >
      <LoginClient />
    </Suspense>
  );
}
