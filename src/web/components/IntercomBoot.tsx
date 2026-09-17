"use client";

// Optional Intercom Messenger (the floating bubble, bottom-right).
//
// When NEXT_PUBLIC_INTERCOM_APP_ID is set in the root .env, this loads the
// Intercom widget script and boots the Messenger. When it is BLANK,
// nothing loads and the built-in ZeroQueue chat is the only interface.
//
// The two chats can coexist: the built-in chat is where the attachment/OCR
// demo lives; the Messenger is the production channel whose messages flow
// through the webhook (app/api/intercom_webhook.py).
import { useEffect } from "react";

declare global {
  interface Window {
    Intercom?: any;
    intercomSettings?: any;
  }
}

const APP_ID = process.env.NEXT_PUBLIC_INTERCOM_APP_ID || "";

export default function IntercomBoot() {
  useEffect(() => {
    if (!APP_ID) return; // blank app id -> no Messenger, custom chat only
    const w = window as any;
    if (typeof w.Intercom === "function") {
      // Widget already loaded (e.g. hot reload): just refresh it.
      w.Intercom("reattach_activator");
      w.Intercom("update", w.intercomSettings);
    } else {
      // Standard Intercom loader: queue calls until the widget script loads.
      const queue: any[] = [];
      const shim: any = (...args: any[]) => queue.push(args);
      shim.q = queue;
      w.Intercom = shim;
      const s = document.createElement("script");
      s.type = "text/javascript";
      s.async = true;
      s.src = `https://widget.intercom.io/widget/${APP_ID}`;
      const first = document.getElementsByTagName("script")[0];
      first.parentNode?.insertBefore(s, first);
    }
    // Safe to call before the script finishes loading - it is queued.
    w.Intercom("boot", { app_id: APP_ID });
    return () => {
      try {
        w.Intercom && w.Intercom("shutdown");
      } catch {
        /* widget never loaded - nothing to shut down */
      }
    };
  }, []);
  return null; // this component renders nothing itself
}
