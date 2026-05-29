import Link from 'next/link';

export default function ForgotPasswordPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-black px-4 py-20 text-white">
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/20 via-slate-950 to-black" />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl">
        <h1 className="text-2xl font-semibold">Reset your password</h1>
        <p className="mt-3 text-sm text-white/70">
          This placeholder page is ready for your real password reset flow.
        </p>
        <div className="mt-6 flex gap-3">
          <Link
            href="/login"
            className="rounded-full bg-white px-5 py-2 text-sm font-medium text-black transition hover:bg-white/90"
          >
            Back to login
          </Link>
          <Link
            href="/signup"
            className="rounded-full border border-white/15 px-5 py-2 text-sm font-medium text-white/80 transition hover:bg-white/10 hover:text-white"
          >
            Create account
          </Link>
        </div>
      </div>
    </main>
  );
}
