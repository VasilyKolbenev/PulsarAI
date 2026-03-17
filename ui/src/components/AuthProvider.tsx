import { useState, useCallback, useEffect, type ReactNode } from "react"
import {
  AuthContext,
  type User,
  getStoredToken,
  getStoredUser,
  storeAuth,
  clearAuth,
} from "@/lib/auth"
import { setApiKey } from "@/api/client"

const BASE = "/api/v1"

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser)
  const [token, setToken] = useState<string | null>(getStoredToken)

  // Keep the API client in sync with the current token
  useEffect(() => {
    setApiKey(token)
  }, [token])

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `Login failed (${res.status})`)
    }
    const data = await res.json()
    storeAuth(data.access_token, data.refresh_token, data.user)
    setToken(data.access_token)
    setUser(data.user)
  }, [])

  const register = useCallback(async (email: string, password: string, name: string) => {
    const res = await fetch(`${BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `Registration failed (${res.status})`)
    }
    const data = await res.json()
    storeAuth(data.access_token, data.refresh_token, data.user)
    setToken(data.access_token)
    setUser(data.user)
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
