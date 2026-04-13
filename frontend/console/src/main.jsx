import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ParentPortal from './portals/parent/ParentPortal.jsx'

function Router() {
  const path = window.location.pathname;

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

  // Fallback: legacy ?center= query param with role toggle
  return <App />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Router />
  </StrictMode>,
)
