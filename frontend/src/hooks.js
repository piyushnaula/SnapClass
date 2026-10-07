import { useCallback, useEffect, useState } from 'react'

/**
 * Load data when a component appears (and when `deps` change).
 *   const { data, error, loading, reload } = useLoad(() => api('/classes'), [])
 */
export function useLoad(loader, deps) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  // Re-create the loader only when `deps` change (like useEffect's dependency list).
  const load = useCallback(loader, deps)

  const reload = useCallback(async () => {
    try {
      setData(await load())
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [load])

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, loading, reload, setData }
}

/** Call `callback` every `ms` milliseconds while `active` is true (used for polling). */
export function useInterval(callback, ms, active) {
  useEffect(() => {
    if (!active) return undefined
    const id = setInterval(callback, ms)
    return () => clearInterval(id)
  }, [callback, ms, active])
}
