import { useEffect, useState } from 'react'
import { describeHealth } from './health.ts'

// Slice 1 placeholder page: proves the web -> /api proxy -> FastAPI path works.
// The real dashboard arrives in Slice 6a.
export default function App() {
  const [apiStatus, setApiStatus] = useState('Checking the API...')

  useEffect(() => {
    fetch('/api/v1/health')
      .then((response) => response.json())
      .then((body: unknown) => setApiStatus(describeHealth(body)))
      .catch(() => setApiStatus("Can't reach the API"))
  }, [])

  return (
    <main>
      <h1>Fitness Tracker</h1>
      <p>{apiStatus}</p>
    </main>
  )
}
