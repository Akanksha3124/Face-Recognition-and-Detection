import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import type { PublicRole } from "@/types/auth";

// Matches RegisterRequest.role on the backend — ADMIN is deliberately
// not offered here (see docs/api.md for why).
const PUBLIC_ROLES: { value: PublicRole; label: string }[] = [
  { value: "INVESTIGATOR", label: "Investigator" },
  { value: "DISASTER_RESPONDER", label: "Disaster Responder" },
  { value: "VERIFIER", label: "Verifier" },
];

export function RegisterPage() {
  const { register, login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<PublicRole>("INVESTIGATOR");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register({ email, password, role });
      // Registration doesn't return tokens (see auth_service.py) — log
      // in immediately afterward so the person isn't asked to type
      // their password twice in a row.
      await login({ email, password });
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setError("That email is already registered.");
      } else if (status === 422) {
        setError("Password must be at least 8 characters.");
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-base font-medium text-slate-800">Create an account</h2>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm text-slate-600 mb-1" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm text-slate-600 mb-1" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
        />
        <p className="text-xs text-slate-400 mt-1">At least 8 characters.</p>
      </div>

      <div>
        <label className="block text-sm text-slate-600 mb-1" htmlFor="role">
          Role
        </label>
        <select
          id="role"
          value={role}
          onChange={(e) => setRole(e.target.value as PublicRole)}
          className="w-full border border-slate-300 rounded px-3 py-2 text-sm bg-white"
        >
          {PUBLIC_ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full bg-slate-800 text-white text-sm rounded py-2 disabled:opacity-50"
      >
        {isSubmitting ? "Creating account…" : "Register"}
      </button>

      <p className="text-sm text-slate-500 text-center">
        Already have an account? <Link to="/login" className="text-slate-800 underline">Log in</Link>
      </p>
    </form>
  );
}
