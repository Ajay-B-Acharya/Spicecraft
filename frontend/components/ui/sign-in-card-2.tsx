"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useTransform,
} from "framer-motion";
import { ArrowRight, Eye, EyeOff, Lock, Mail, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { GoogleAuthProvider, signInWithPopup } from "firebase/auth";

import { auth } from "@/lib/firebase";
import { cn } from "@/lib/utils";

type AuthMode = "signin" | "signup";

const DEMO_USER_STORAGE_KEY = "spicecraft-demo-user";

type SignInCardTwoProps = {
  mode?: AuthMode;
};

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "file:text-foreground placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground dark:bg-input/30 border-input flex h-10 w-full min-w-0 rounded-md border bg-transparent px-3 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}

export function SignInCardTwo({ mode = "signin" }: SignInCardTwoProps) {
  const isSignup = mode === "signup";
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [focusedInput, setFocusedInput] = useState<string | null>(null);
  const [rememberMe, setRememberMe] = useState(false);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const rotateX = useTransform(mouseY, [-300, 300], [10, -10]);
  const rotateY = useTransform(mouseX, [-300, 300], [-10, 10]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    mouseX.set(e.clientX - rect.left - rect.width / 2);
    mouseY.set(e.clientY - rect.top - rect.height / 2);
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError(null);
    setIsLoading(true);

    try {
      const fallbackName = isSignup ? name.trim() : "";
      const fallbackEmail = email.trim();
      window.localStorage.setItem(
        DEMO_USER_STORAGE_KEY,
        JSON.stringify({
          name: fallbackName || undefined,
          email: fallbackEmail || undefined,
        }),
      );
    } catch {
      // Ignore localStorage failures and continue with demo flow.
    }

    window.setTimeout(() => {
      setIsLoading(false);
      router.push("/dashboard");
    }, 900);
  };

  const handleGoogleSignIn = async () => {
    setAuthError(null);
    setIsGoogleLoading(true);

    try {
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      await signInWithPopup(auth, provider);
      router.push("/dashboard");
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Google sign-in failed. Please try again.";
      setAuthError(message);
    } finally {
      setIsGoogleLoading(false);
    }
  };

  const title = isSignup ? "Create Account" : "Welcome Back";
  const subtitle = isSignup
    ? "Sign up to start building smarter circuits with SpiceCraft"
    : "Sign in to continue to SpiceCraft";
  const submitLabel = isSignup ? "Create Account" : "Sign In";
  const alternateHref = isSignup ? "/login" : "/signup";
  const alternateLabel = isSignup
    ? "Already have an account?"
    : "Don't have an account?";
  const alternateAction = isSignup ? "Log in" : "Sign up";

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-black px-4 py-20">
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/25 via-slate-950 to-black" />
      <div
        className="absolute inset-0 opacity-[0.03] mix-blend-soft-light"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E\")",
          backgroundSize: "200px 200px",
        }}
      />
      <div className="absolute top-0 left-1/2 h-[60vh] w-[120vh] -translate-x-1/2 rounded-b-[50%] bg-indigo-400/20 blur-[80px]" />
      <motion.div
        className="absolute top-0 left-1/2 h-[60vh] w-[100vh] -translate-x-1/2 rounded-b-full bg-cyan-300/15 blur-[60px]"
        animate={{ opacity: [0.15, 0.3, 0.15], scale: [0.98, 1.02, 0.98] }}
        transition={{ duration: 8, repeat: Infinity, repeatType: "mirror" }}
      />
      <motion.div
        className="absolute bottom-0 left-1/2 h-[90vh] w-[90vh] -translate-x-1/2 rounded-t-full bg-indigo-500/15 blur-[60px]"
        animate={{ opacity: [0.25, 0.45, 0.25], scale: [1, 1.08, 1] }}
        transition={{
          duration: 6,
          repeat: Infinity,
          repeatType: "mirror",
          delay: 1,
        }}
      />
      <div className="absolute top-1/4 left-1/4 h-80 w-80 rounded-full bg-white/5 blur-[100px] opacity-40" />
      <div className="absolute right-1/4 bottom-1/4 h-80 w-80 rounded-full bg-cyan-300/5 blur-[100px] opacity-40" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="relative z-10 w-full max-w-sm"
        style={{ perspective: 1500 }}
      >
        <motion.div
          className="relative"
          style={{ rotateX, rotateY }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          whileHover={{ z: 10 }}
        >
          <div className="group relative">
            <motion.div
              className="absolute -inset-px rounded-2xl opacity-0 transition-opacity duration-700 group-hover:opacity-70"
              animate={{
                boxShadow: [
                  "0 0 10px 2px rgba(255,255,255,0.03)",
                  "0 0 15px 5px rgba(255,255,255,0.05)",
                  "0 0 10px 2px rgba(255,255,255,0.03)",
                ],
                opacity: [0.2, 0.4, 0.2],
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                ease: "easeInOut",
                repeatType: "mirror",
              }}
            />

            <div className="absolute -inset-px overflow-hidden rounded-2xl">
              <motion.div
                className="absolute top-0 left-0 h-[3px] w-1/2 bg-gradient-to-r from-transparent via-white to-transparent opacity-70"
                initial={{ filter: "blur(2px)" }}
                animate={{
                  left: ["-50%", "100%"],
                  opacity: [0.3, 0.7, 0.3],
                  filter: ["blur(1px)", "blur(2.5px)", "blur(1px)"],
                }}
                transition={{
                  left: {
                    duration: 2.5,
                    ease: "easeInOut",
                    repeat: Infinity,
                    repeatDelay: 1,
                  },
                  opacity: {
                    duration: 1.2,
                    repeat: Infinity,
                    repeatType: "mirror",
                  },
                  filter: {
                    duration: 1.5,
                    repeat: Infinity,
                    repeatType: "mirror",
                  },
                }}
              />
              <motion.div
                className="absolute top-0 right-0 h-1/2 w-[3px] bg-gradient-to-b from-transparent via-white to-transparent opacity-70"
                initial={{ filter: "blur(2px)" }}
                animate={{
                  top: ["-50%", "100%"],
                  opacity: [0.3, 0.7, 0.3],
                  filter: ["blur(1px)", "blur(2.5px)", "blur(1px)"],
                }}
                transition={{
                  top: {
                    duration: 2.5,
                    ease: "easeInOut",
                    repeat: Infinity,
                    repeatDelay: 1,
                    delay: 0.6,
                  },
                  opacity: {
                    duration: 1.2,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: 0.6,
                  },
                  filter: {
                    duration: 1.5,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: 0.6,
                  },
                }}
              />
              <motion.div
                className="absolute right-0 bottom-0 h-[3px] w-1/2 bg-gradient-to-r from-transparent via-white to-transparent opacity-70"
                initial={{ filter: "blur(2px)" }}
                animate={{
                  right: ["-50%", "100%"],
                  opacity: [0.3, 0.7, 0.3],
                  filter: ["blur(1px)", "blur(2.5px)", "blur(1px)"],
                }}
                transition={{
                  right: {
                    duration: 2.5,
                    ease: "easeInOut",
                    repeat: Infinity,
                    repeatDelay: 1,
                    delay: 1.2,
                  },
                  opacity: {
                    duration: 1.2,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: 1.2,
                  },
                  filter: {
                    duration: 1.5,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: 1.2,
                  },
                }}
              />
              <motion.div
                className="absolute bottom-0 left-0 h-1/2 w-[3px] bg-gradient-to-b from-transparent via-white to-transparent opacity-70"
                initial={{ filter: "blur(2px)" }}
                animate={{
                  bottom: ["-50%", "100%"],
                  opacity: [0.3, 0.7, 0.3],
                  filter: ["blur(1px)", "blur(2.5px)", "blur(1px)"],
                }}
                transition={{
                  bottom: {
                    duration: 2.5,
                    ease: "easeInOut",
                    repeat: Infinity,
                    repeatDelay: 1,
                    delay: 1.8,
                  },
                  opacity: {
                    duration: 1.2,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: 1.8,
                  },
                  filter: {
                    duration: 1.5,
                    repeat: Infinity,
                    repeatType: "mirror",
                    delay: 1.8,
                  },
                }}
              />
            </div>

            <div className="absolute -inset-[0.5px] rounded-2xl bg-gradient-to-r from-white/[0.03] via-white/[0.07] to-white/[0.03] opacity-0 transition-opacity duration-500 group-hover:opacity-70" />

            <div className="relative overflow-hidden rounded-2xl border border-white/[0.05] bg-black/40 p-6 shadow-2xl backdrop-blur-xl">
              <div
                className="absolute inset-0 opacity-[0.03]"
                style={{
                  backgroundImage:
                    "linear-gradient(135deg, white 0.5px, transparent 0.5px), linear-gradient(45deg, white 0.5px, transparent 0.5px)",
                  backgroundSize: "30px 30px",
                }}
              />

              <div className="relative mb-5 space-y-1 text-center">
                <motion.div
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", duration: 0.8 }}
                  className="relative mx-auto flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-white/10"
                >
                  <span className="bg-gradient-to-b from-white to-white/70 bg-clip-text text-lg font-bold text-transparent">
                    S
                  </span>
                  <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent opacity-50" />
                </motion.div>

                <motion.h1
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="bg-gradient-to-b from-white to-white/80 bg-clip-text text-xl font-bold text-transparent"
                >
                  {title}
                </motion.h1>

                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 }}
                  className="text-xs text-white/60"
                >
                  {subtitle}
                </motion.p>
              </div>

              <form onSubmit={handleSubmit} className="relative space-y-4">
                <motion.div className="space-y-3">
                  {isSignup ? (
                    <motion.div
                      className={`relative ${focusedInput === "name" ? "z-10" : ""}`}
                      whileHover={{ scale: 1.01 }}
                      transition={{
                        type: "spring",
                        stiffness: 400,
                        damping: 25,
                      }}
                    >
                      <div className="relative flex items-center overflow-hidden rounded-lg">
                        <User
                          className={cn(
                            "absolute left-3 h-4 w-4 transition-all duration-300",
                            focusedInput === "name"
                              ? "text-white"
                              : "text-white/40",
                          )}
                        />
                        <Input
                          type="text"
                          placeholder="Full name"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          onFocus={() => setFocusedInput("name")}
                          onBlur={() => setFocusedInput(null)}
                          className="border-transparent bg-white/5 pl-10 pr-3 text-white placeholder:text-white/30 focus:border-white/20 focus:bg-white/10"
                        />
                        {focusedInput === "name" ? (
                          <motion.div
                            layoutId="input-highlight"
                            className="absolute inset-0 -z-10 bg-white/5"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                          />
                        ) : null}
                      </div>
                    </motion.div>
                  ) : null}

                  <motion.div
                    className={`relative ${focusedInput === "email" ? "z-10" : ""}`}
                    whileHover={{ scale: 1.01 }}
                    transition={{ type: "spring", stiffness: 400, damping: 25 }}
                  >
                    <div className="relative flex items-center overflow-hidden rounded-lg">
                      <Mail
                        className={cn(
                          "absolute left-3 h-4 w-4 transition-all duration-300",
                          focusedInput === "email"
                            ? "text-white"
                            : "text-white/40",
                        )}
                      />
                      <Input
                        type="email"
                        placeholder="Email address"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        onFocus={() => setFocusedInput("email")}
                        onBlur={() => setFocusedInput(null)}
                        className="border-transparent bg-white/5 pl-10 pr-3 text-white placeholder:text-white/30 focus:border-white/20 focus:bg-white/10"
                      />
                      {focusedInput === "email" ? (
                        <motion.div
                          layoutId="input-highlight"
                          className="absolute inset-0 -z-10 bg-white/5"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        />
                      ) : null}
                    </div>
                  </motion.div>

                  <motion.div
                    className={`relative ${focusedInput === "password" ? "z-10" : ""}`}
                    whileHover={{ scale: 1.01 }}
                    transition={{ type: "spring", stiffness: 400, damping: 25 }}
                  >
                    <div className="relative flex items-center overflow-hidden rounded-lg">
                      <Lock
                        className={cn(
                          "absolute left-3 h-4 w-4 transition-all duration-300",
                          focusedInput === "password"
                            ? "text-white"
                            : "text-white/40",
                        )}
                      />
                      <Input
                        type={showPassword ? "text" : "password"}
                        placeholder="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onFocus={() => setFocusedInput("password")}
                        onBlur={() => setFocusedInput(null)}
                        className="border-transparent bg-white/5 pl-10 pr-10 text-white placeholder:text-white/30 focus:border-white/20 focus:bg-white/10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((value) => !value)}
                        className="absolute right-3 text-white/40 transition-colors duration-300 hover:text-white"
                        aria-label={
                          showPassword ? "Hide password" : "Show password"
                        }
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                      {focusedInput === "password" ? (
                        <motion.div
                          layoutId="input-highlight"
                          className="absolute inset-0 -z-10 bg-white/5"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        />
                      ) : null}
                    </div>
                  </motion.div>

                  {isSignup ? (
                    <motion.div
                      className={`relative ${focusedInput === "confirmPassword" ? "z-10" : ""}`}
                      whileHover={{ scale: 1.01 }}
                      transition={{
                        type: "spring",
                        stiffness: 400,
                        damping: 25,
                      }}
                    >
                      <div className="relative flex items-center overflow-hidden rounded-lg">
                        <Lock
                          className={cn(
                            "absolute left-3 h-4 w-4 transition-all duration-300",
                            focusedInput === "confirmPassword"
                              ? "text-white"
                              : "text-white/40",
                          )}
                        />
                        <Input
                          type={showConfirmPassword ? "text" : "password"}
                          placeholder="Confirm password"
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          onFocus={() => setFocusedInput("confirmPassword")}
                          onBlur={() => setFocusedInput(null)}
                          className="border-transparent bg-white/5 pl-10 pr-10 text-white placeholder:text-white/30 focus:border-white/20 focus:bg-white/10"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setShowConfirmPassword((value) => !value)
                          }
                          className="absolute right-3 text-white/40 transition-colors duration-300 hover:text-white"
                          aria-label={
                            showConfirmPassword
                              ? "Hide confirm password"
                              : "Show confirm password"
                          }
                        >
                          {showConfirmPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                        {focusedInput === "confirmPassword" ? (
                          <motion.div
                            layoutId="input-highlight"
                            className="absolute inset-0 -z-10 bg-white/5"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                          />
                        ) : null}
                      </div>
                    </motion.div>
                  ) : null}
                </motion.div>

                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center space-x-2">
                    <div className="relative">
                      <input
                        id="remember-me"
                        name="remember-me"
                        type="checkbox"
                        checked={rememberMe}
                        onChange={() => setRememberMe((value) => !value)}
                        className="h-4 w-4 appearance-none rounded border border-white/20 bg-white/5 transition-all duration-200 checked:border-white checked:bg-white focus:outline-none focus:ring-1 focus:ring-white/30"
                      />
                      {rememberMe ? (
                        <motion.div
                          initial={{ opacity: 0, scale: 0.5 }}
                          animate={{ opacity: 1, scale: 1 }}
                          className="pointer-events-none absolute inset-0 flex items-center justify-center text-black"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        </motion.div>
                      ) : null}
                    </div>
                    <label
                      htmlFor="remember-me"
                      className="text-xs text-white/60 transition-colors duration-200 hover:text-white/80"
                    >
                      {isSignup ? "Send me product updates" : "Remember me"}
                    </label>
                  </div>

                  <div className="text-xs">
                    <Link
                      href="/forgot-password"
                      className="text-white/60 transition-colors duration-200 hover:text-white"
                    >
                      Forgot password?
                    </Link>
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="submit"
                  disabled={isLoading}
                  className="group/button relative mt-5 w-full"
                >
                  <div className="absolute inset-0 rounded-lg bg-white/10 blur-lg opacity-0 transition-opacity duration-300 group-hover/button:opacity-70" />
                  <div className="relative flex h-10 items-center justify-center overflow-hidden rounded-lg bg-white font-medium text-black transition-all duration-300">
                    <motion.div
                      className="absolute inset-0 -z-10 bg-gradient-to-r from-white/0 via-white/30 to-white/0"
                      animate={{ x: ["-100%", "100%"] }}
                      transition={{
                        duration: 1.5,
                        ease: "easeInOut",
                        repeat: Infinity,
                        repeatDelay: 1,
                      }}
                      style={{
                        opacity: isLoading ? 1 : 0,
                        transition: "opacity 0.3s ease",
                      }}
                    />

                    <AnimatePresence mode="wait">
                      {isLoading ? (
                        <motion.div
                          key="loading"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="flex items-center justify-center"
                        >
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-black/70 border-t-transparent" />
                        </motion.div>
                      ) : (
                        <motion.span
                          key={submitLabel}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="flex items-center justify-center gap-1 text-sm font-medium"
                        >
                          {submitLabel}
                          <ArrowRight className="h-3 w-3 transition-transform duration-300 group-hover/button:translate-x-1" />
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.button>

                <div className="my-5 flex items-center">
                  <div className="flex-grow border-t border-white/5" />
                  <motion.span
                    className="mx-3 text-xs text-white/40"
                    initial={{ opacity: 0.7 }}
                    animate={{ opacity: [0.7, 0.9, 0.7] }}
                    transition={{
                      duration: 3,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  >
                    or
                  </motion.span>
                  <div className="flex-grow border-t border-white/5" />
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={handleGoogleSignIn}
                  disabled={isGoogleLoading}
                  className="group/google relative w-full disabled:cursor-not-allowed disabled:opacity-70"
                >
                  <div className="absolute inset-0 rounded-lg bg-white/5 blur opacity-0 transition-opacity duration-300 group-hover/google:opacity-70" />
                  <div className="relative flex h-10 items-center justify-center gap-2 overflow-hidden rounded-lg border border-white/10 bg-white/5 font-medium text-white transition-all duration-300 hover:border-white/20">
                    <div className="flex h-4 w-4 items-center justify-center text-white/80 transition-colors duration-300 group-hover/google:text-white">
                      G
                    </div>
                    <span className="text-xs text-white/80 transition-colors group-hover/google:text-white">
                      {isGoogleLoading
                        ? "Connecting..."
                        : isSignup
                          ? "Continue with Google"
                          : "Sign in with Google"}
                    </span>
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/5 to-white/0"
                      initial={{ x: "-100%" }}
                      whileHover={{ x: "100%" }}
                      transition={{ duration: 1, ease: "easeInOut" }}
                    />
                  </div>
                </motion.button>

                {authError ? (
                  <p className="text-center text-xs text-red-300/90">
                    {authError}
                  </p>
                ) : null}

                <motion.p
                  className="mt-4 text-center text-xs text-white/60"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 }}
                >
                  {alternateLabel}{" "}
                  <Link
                    href={alternateHref}
                    className="group/signup relative inline-block"
                  >
                    <span className="relative z-10 font-medium text-white transition-colors duration-300 group-hover/signup:text-white/70">
                      {alternateAction}
                    </span>
                    <span className="absolute bottom-0 left-0 h-px w-0 bg-white transition-all duration-300 group-hover/signup:w-full" />
                  </Link>
                </motion.p>
              </form>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}

export function Component(props: SignInCardTwoProps) {
  return <SignInCardTwo {...props} />;
}
