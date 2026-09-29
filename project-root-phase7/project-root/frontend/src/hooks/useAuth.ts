// Re-exported from auth/ so components can `import { useAuth } from
// "@/hooks/useAuth"` alongside other hooks, without every auth-related
// component needing to know the context itself lives in src/auth/.
export { useAuth } from "@/auth/AuthContext";
