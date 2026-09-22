import { useEffect, useMemo, useState } from 'react'

// Plain data-fetching + a plain table. No styling effort by design -
// the brief is explicit that a plain table is the correct answer here.

function App() {
  const [orgs, setOrgs] = useState([])
  const [org, setOrg] = useState('')
  const [reasons, setReasons] = useState([])
  const [results, setResults] = useState([])
  const [reasonFilter, setReasonFilter] = useState('ALL')
  const [sortDirection, setSortDirection] = useState('desc')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/orgs/')
      .then((res) => res.json())
      .then((data) => {
        setOrgs(data.orgs)
        setOrg(data.orgs[0] ?? '')
      })
      .catch(() => setError('Could not load orgs from the API.'))
  }, [])

  useEffect(() => {
    if (!org) return
    setLoading(true)
    fetch(`/api/disagreements/?org=${encodeURIComponent(org)}`)
      .then((res) => res.json())
      .then((data) => {
        setReasons(data.reasons)
        setResults(data.results)
        setError('')
      })
      .catch(() => setError('Could not load disagreements from the API.'))
      .finally(() => setLoading(false))
  }, [org])

  const visibleRows = useMemo(() => {
    const filtered =
      reasonFilter === 'ALL' ? results : results.filter((row) => row.reason === reasonFilter)

    // a_value isn't always numeric (e.g. LOCATION_MISMATCH stores a location id there),
    // so sort as numbers when possible and fall back to plain string sort otherwise
    const sorted = [...filtered].sort((a, b) => {
      const numA = parseFloat(a.a_value)
      const numB = parseFloat(b.a_value)
      const bothNumeric = !Number.isNaN(numA) && !Number.isNaN(numB)
      const cmp = bothNumeric ? numA - numB : a.a_value.localeCompare(b.a_value)
      return sortDirection === 'asc' ? cmp : -cmp
    })

    return sorted
  }, [results, reasonFilter, sortDirection])

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '1.5rem', maxWidth: '1100px' }}>
      <h1>DealerOS reconciliation</h1>
      <p>Records where System A and System B disagree, one tenant at a time.</p>

      <div style={{ display: 'flex', gap: '1rem', margin: '1rem 0' }}>
        <label>
          Org (tenant):{' '}
          <select value={org} onChange={(e) => setOrg(e.target.value)}>
            {orgs.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>

        <label>
          Reason:{' '}
          <select value={reasonFilter} onChange={(e) => setReasonFilter(e.target.value)}>
            <option value="ALL">All</option>
            {reasons.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p style={{ color: 'red' }}>{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading && !error && (
        <table border="1" cellPadding="6" style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th>Reason</th>
              <th>Record</th>
              <th>Location</th>
              <th
                style={{ cursor: 'pointer' }}
                onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              >
                System A value {sortDirection === 'asc' ? '▲' : '▼'}
              </th>
              <th>System B value</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr key={`${row.record_id}-${row.reason}-${i}`}>
                <td>{row.reason}</td>
                <td>{row.record_id}</td>
                <td>{row.location_id}</td>
                <td>{row.a_value || '—'}</td>
                <td>{row.b_value || '—'}</td>
                <td>{row.detail}</td>
              </tr>
            ))}
            {visibleRows.length === 0 && (
              <tr>
                <td colSpan={6}>No disagreements for this org/reason.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default App
