import { useEffect, useState } from 'react'
import DeploymentStatus from '../components/DeploymentStatus'
import ManualConfigurationForm from '../components/ManualConfigurationForm'
import { DeviceAPI, ManualAPI } from '../services/api'

export default function ManualConfiguration() {
  const [devices, setDevices] = useState([])
  const [result, setResult] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => { DeviceAPI.list().then((r) => setDevices(r.data)) }, [])

  const submit = async (payload) => {
    setErr(''); setResult(null)
    try {
      const r = await ManualAPI.run(payload)
      setResult(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Configuration failed')
    }
  }

  return (
    <div className="grid" style={{ gap: 16 }}>
      <h2 style={{ margin: 0 }}>Manual Configuration</h2>
      <ManualConfigurationForm devices={devices} onSubmit={submit} />
      {err && <div className="error">{err}</div>}
      {result && <DeploymentStatus results={[result]} />}
    </div>
  )
}
