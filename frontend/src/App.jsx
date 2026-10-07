import { useEffect, useState } from 'react'
import { api, clearAuth, getAuth, saveAuth } from './api.js'
import Layout from './components/Layout.jsx'
import { useToast } from './components/Toast.jsx'
import { matchRoute, navigate, useRoute } from './router.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import JoinPage from './pages/JoinPage.jsx'
import ClassesPage from './pages/teacher/ClassesPage.jsx'
import ClassPage from './pages/teacher/ClassPage.jsx'
import SessionPage from './pages/teacher/SessionPage.jsx'
import StudentHome from './pages/student/StudentHome.jsx'
import BiometricsPage from './pages/student/BiometricsPage.jsx'
import AdminPage from './pages/admin/AdminPage.jsx'

export default function App() {
  const path = useRoute()
  const [user, setUser] = useState(() => getAuth()?.user || null)
  const toast = useToast()

  // api.js fires this event when the session cannot be refreshed any more.
  useEffect(() => {
    const onLogout = () => {
      setUser(null)
      toast('Your session has ended. Please sign in again.', 'error')
    }
    window.addEventListener('snapclass:logout', onLogout)
    return () => window.removeEventListener('snapclass:logout', onLogout)
  }, [toast])

  // Remember the signed-in user (tokens + profile).
  function signIn(data) {
    saveAuth(data)
    setUser(data.user)
  }

  function handleLogin(data, nextPath = '/', message = null) {
    signIn(data)
    navigate(nextPath)
    toast(message || `Welcome, ${data.user.full_name.split(' ')[0]}`)
  }

  async function handleLogout() {
    const refreshToken = getAuth()?.refresh_token
    try {
      if (refreshToken) await api('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } })
    } catch {
      // even if the server call fails, forget the tokens locally
    }
    clearAuth()
    setUser(null)
    navigate('/')
    toast('You have signed out.')
  }

  // The join link works whether or not someone is logged in.
  const join = matchRoute('/join/:code', path)
  if (join) {
    return (
      <Layout user={user} path={path} onLogout={handleLogout}>
        <JoinPage code={join.code} user={user} onSignedIn={signIn} />
      </Layout>
    )
  }

  if (!user) {
    if (path === '/register') {
      return <RegisterPage onRegistered={(data) => handleLogin(data, '/biometrics', 'Your account is ready. Next, set up your face.')} />
    }
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <Layout user={user} path={path} onLogout={handleLogout}>
      <PageFor user={user} path={path} />
    </Layout>
  )
}

// Pick the page to show from the user's role and the current URL.
function PageFor({ user, path }) {
  if (user.role === 'TEACHER') {
    const classMatch = matchRoute('/classes/:id', path)
    if (classMatch) return <ClassPage key={classMatch.id} classId={classMatch.id} />
    const sessionMatch = matchRoute('/sessions/:id', path)
    if (sessionMatch) return <SessionPage key={sessionMatch.id} sessionId={sessionMatch.id} />
    return <ClassesPage />
  }
  if (user.role === 'STUDENT') {
    if (path === '/biometrics') return <BiometricsPage />
    return <StudentHome />
  }
  return <AdminPage />
}
