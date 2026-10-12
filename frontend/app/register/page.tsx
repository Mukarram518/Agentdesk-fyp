"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/AuthContext";
import { isApiClientError, apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated, isLoading: authLoading } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [authLoading, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      setErrorMessage("Please enter a valid email address.");
      return;
    }

    if (!password) {
      setErrorMessage("Please enter a password.");
      return;
    }

    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match. Please verify both fields.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register({
        email: trimmedEmail,
        password,
        full_name: trimmedName || undefined,
      });
      router.replace("/");
    } catch (err: unknown) {
      if (isApiClientError(err)) {
        if (err.statusCode === 409) {
          setErrorMessage("An account with this email address already exists. Please sign in instead.");
        } else if (err.statusCode === 422) {
          setErrorMessage(err.message || "Password must be at least 8 characters and include numbers or symbols.");
        } else if (err.statusCode === 429) {
          setErrorMessage("Too many registration attempts. Please wait a moment.");
        } else {
          setErrorMessage(err.message || "Registration failed. Please check your details.");
        }
      } else {
        setErrorMessage("Network error connecting to AgentDesk backend.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = `${apiClient.baseUrl}/api/v1/auth/google`;
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-warm-ivory">
        <div className="w-8 h-8 rounded-full border-2 border-cherry border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8 bg-warm-ivory">
      {/* Brand Header */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-cherry text-white font-bold text-xl shadow-md shadow-cherry/20 mb-4">
          A
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-main-text">
          Create your AgentDesk account
        </h2>
        <p className="mt-2 text-xs sm:text-sm text-secondary-text max-w">
          Get started with multi-agent AI for your business
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-card-bg py-8 px-6 sm:px-10 rounded-2xl border border-border-main shadow-sm">
          {/* Error Alert */}
          {errorMessage && (
            <div
              role="alert"
              className="mb-6 p-3.5 rounded-lg bg-status-error/10 border border-status-error/20 text-status-error text-xs flex items-start gap-2.5"
            >
              <svg
                className="w-4 h-4 shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <span className="font-medium">{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Full Name */}
            <div>
              <label
                htmlFor="fullName"
                className="block text-xs font-semibold text-main-text uppercase tracking-wider mb-1.5"
              >
                Full Name
              </label>
              <input
                id="fullName"
                name="fullName"
                type="text"
                autoComplete="name"
                disabled={isSubmitting}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Mukarram Ali"
                className="w-full px-3.5 py-2 rounded-lg bg-warm-ivory border border-border-main text-sm text-main-text placeholder:text-muted-text focus:outline-none focus:border-cherry focus:ring-1 focus:ring-cherry transition disabled:opacity-50"
              />
            </div>

            {/* Email Address */}
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-main-text uppercase tracking-wider mb-1.5"
              >
                Email Address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                disabled={isSubmitting}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@example.com"
                className="w-full px-3.5 py-2 rounded-lg bg-warm-ivory border border-border-main text-sm text-main-text placeholder:text-muted-text focus:outline-none focus:border-cherry focus:ring-1 focus:ring-cherry transition disabled:opacity-50"
              />
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-main-text uppercase tracking-wider mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  disabled={isSubmitting}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="w-full pl-3.5 pr-10 py-2 rounded-lg bg-warm-ivory border border-border-main text-sm text-main-text placeholder:text-muted-text focus:outline-none focus:border-cherry focus:ring-1 focus:ring-cherry transition disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-text hover:text-main-text text-xs transition"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-xs font-semibold text-main-text uppercase tracking-wider mb-1.5"
              >
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                required
                disabled={isSubmitting}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                className="w-full px-3.5 py-2 rounded-lg bg-warm-ivory border border-border-main text-sm text-main-text placeholder:text-muted-text focus:outline-none focus:border-cherry focus:ring-1 focus:ring-cherry transition disabled:opacity-50"
              />
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                disabled={isSubmitting}
                className="w-full py-2.5 text-sm font-semibold tracking-wide justify-center shadow-sm"
              >
                {isSubmitting ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Creating account...
                  </span>
                ) : (
                  "Create Account"
                )}
              </Button>
            </div>
          </form>

          {/* Social Login Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border-soft" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-card-bg px-2.5 text-muted-text">
                Or continue with
              </span>
            </div>
          </div>

          {/* Google Sign In Button */}
          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={isSubmitting}
            className="w-full inline-flex items-center justify-center gap-2.5 px-4 py-2 border border-border-main rounded-lg bg-white text-xs font-semibold text-main-text hover:bg-cherry-soft hover:border-cherry/40 transition shadow-2xs disabled:opacity-50"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>Sign up with Google</span>
          </button>

          {/* Login Link */}
          <div className="mt-6 text-center text-xs text-secondary-text">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-semibold text-cherry hover:text-cherry-hover transition underline-offset-2 hover:underline"
            >
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
