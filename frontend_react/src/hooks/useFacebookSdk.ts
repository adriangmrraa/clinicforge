import { useState, useEffect } from 'react';
import { getEnv } from '../utils/env';

declare global {
    interface Window {
        FB: any;
        fbAsyncInit: () => void;
    }
}

export const useFacebookSdk = () => {
    const [isReady, setIsReady] = useState(false);

    useEffect(() => {
        // Use runtime injection (Docker/EasyPanel) with Vite build-time fallback
        const appId = getEnv('VITE_FACEBOOK_APP_ID');
        if (!appId) {
            console.error("[Meta SDK] VITE_FACEBOOK_APP_ID missing (checked window.__ENV__ and import.meta.env)");
            return;
        }

        console.log("[Meta SDK] App ID found, loading SDK...");

        const initParams = {
            appId,
            cookie: true,
            xfbml: true,
            version: 'v22.0'
        };

        // If already loaded, force init
        if (window.FB) {
            try {
                window.FB.init(initParams);
                setIsReady(true);
            } catch (err) {
                console.error("[Meta SDK] Force Init Failed:", err);
                setIsReady(true);
            }
            return;
        }

        // Define the official callback
        window.fbAsyncInit = function () {
            try {
                window.FB.init(initParams);
            } catch (err) {
                console.error("[Meta SDK] Async Init Failed:", err);
            } finally {
                setIsReady(true);
            }
        };

        // Load the script
        const scriptId = 'facebook-jssdk';
        if (document.getElementById(scriptId)) return;

        // Timeout fallback (3s) — unblock UI even if SDK fails
        const timeoutId = setTimeout(() => {
            console.warn("[Meta SDK] 3s Timeout. Forcing ready.");
            setIsReady(true);
        }, 3000);

        const js = document.createElement('script');
        js.id = scriptId;
        js.src = "https://connect.facebook.net/es_LA/sdk.js";
        js.onerror = () => {
            console.error("[Meta SDK] Script load failed (ad blocker?)");
            setIsReady(true);
        };

        const fjs = document.getElementsByTagName('script')[0];
        if (fjs && fjs.parentNode) {
            fjs.parentNode.insertBefore(js, fjs);
        } else {
            document.head.appendChild(js);
        }

        return () => clearTimeout(timeoutId);
    }, []);

    return isReady;
};
