"use client";

import { useEffect, useState } from "react";

import { clearSessionToken, loginWithApiKey, rotateApiKey, setSessionToken, whoAmI } from "@/lib/api";

type SessionUser = { user_id: number; org_id: number; role: string; name: string; auth_type: string };

export function SessionPanel() {
  const [apiKey, setApiKey] = useState("");
  const [user, setUser] = useState<SessionUser | null>(null);
  const [msg, setMsg] = useState("");

  async function refresh() {
    try {
      const nextUser = await whoAmI();
      setUser(nextUser);
    } catch {
      setUser(null);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onLogin() {
    if (!apiKey.trim()) {
      setMsg("Provide an API key to create a session.");
      return;
    }
    try {
      const res = await loginWithApiKey(apiKey.trim());
      setSessionToken(res.access_token);
      setMsg(`Session active for ${res.user.name} (${res.user.role}).`);
      setApiKey("");
      setUser(res.user);
    } catch (e) {
      setMsg(`Login failed: ${String(e)}`);
    }
  }

  async function onRotate(scope: "user" | "org") {
    try {
      const res = await rotateApiKey(scope);
      setMsg(`New ${scope} key: ${res.new_api_key}`);
    } catch (e) {
      setMsg(`Rotate failed: ${String(e)}`);
    }
  }

  function onLogout() {
    clearSessionToken();
    setUser(null);
    setMsg("Session cleared.");
  }

  return (
    <div className="session-panel">
      <div className="flex flex-wrap items-center gap-2">
        {user ? (
          <>
            <span className="session-pill">
              {user.name} / {user.role} / org {user.org_id}
            </span>
            <button onClick={onLogout} className="btn-muted px-3 py-2 text-xs">
              Logout
            </button>
            <button onClick={() => onRotate("user")} className="btn-info">
              Rotate User Key
            </button>
            {user.role === "org_admin" ? (
              <button onClick={() => onRotate("org")} className="btn-muted px-3 py-2 text-xs">
                Rotate Org Key
              </button>
            ) : null}
          </>
        ) : (
          <>
            <input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter API key"
              className="hud-input w-full sm:w-72"
            />
            <button onClick={onLogin} className="btn-primary px-4 py-2 text-xs">
              Start Session
            </button>
          </>
        )}
      </div>
      {msg ? <p className="mt-2 text-[11px] text-slate-300/72">{msg}</p> : null}
    </div>
  );
}
