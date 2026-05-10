import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ParentPortal from './portals/parent/ParentPortal.jsx'
import ConsentPage from './portals/ConsentPortal/ConsentPage.jsx'
import Dispatcher from './portals/Dispatcher.jsx'
import PrivacyPolicy from './portals/PrivacyPolicy.jsx'
import { getStoredToken } from './api/client.js'
import { installDynamicManifest } from './utils/dynamicManifest.js'
import { initSentry } from './sentry.js'

initSentry();

// Install per-user manifest on every cold start, BEFORE any redirect or
// component mount. Required for iOS Add-to-Home-Screen — by the time the
// user taps Share → Add to Home Screen, they're usually on a portal page
// (post-redirect from /app), and iOS reads whatever manifest the page
// currently advertises. Static manifest = no token in start_url = "expired"
// loop. This call swaps in the dynamic one immediately.
installDynamicManifest(getStoredToken());

function Router() {
  const path = window.location.pathname;

  // /privacy — static privacy policy (no auth, COPPA-required public page)
  if (path === '/privacy' || path === '/privacy/') {
    return <PrivacyPolicy />;
  }

  // /consent/:token — magic-link consent flow (no bearer auth)
  const consentMatch = path.match(/^\/consent\/([^/]+)/);
  if (consentMatch) {
    return <ConsentPage token={consentMatch[1]} />;
  }

  // /app — PWA dispatcher; captures bootstrap token and routes by role
  if (path === '/app' || path === '/app/') {
    return <Dispatcher />;
  }

  // /parent/:centerId/:childId
  const parentMatch = path.match(/^\/parent\/([^/]+)\/([^/]+)/);
  if (parentMatch) {
    return <ParentPortal centerId={parentMatch[1]} childId={parentMatch[2]} />;
  }

  // /teacher/:centerId/:teacherId → existing App in teacher mode
  const teacherMatch = path.match(/^\/teacher\/([^/]+)\/([^/]+)/);
  if (teacherMatch) {
    return <App forcedRole="teacher" centerId={teacherMatch[1]} teacherId={teacherMatch[2]} />;
  }

  // /director/:centerId → existing App in director mode
  const directorMatch = path.match(/^\/director\/([^/]+)/);
  if (directorMatch) {
    return <App forcedRole="director" centerId={directorMatch[1]} />;
  }

  // Anything else (including /) → dispatcher; it'll redirect or show
  // the "expired link" message based on stored token.
  return <Dispatcher />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router />
  </StrictMode>,
)
